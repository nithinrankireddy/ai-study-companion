import os
import json
import time
from dotenv import load_dotenv

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from google import genai

from .database import get_db, SessionLocal
from .models import Project, Space
from .workspace_routes import get_current_user
from .ai_observability import log_ai_call

load_dotenv()

router = APIRouter(prefix="/assessment", tags=["Assessment"])


# -----------------------------
# Gemini
# -----------------------------

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured"
        )

    return genai.Client(api_key=api_key)


# -----------------------------
# Request Models
# -----------------------------

class GenerateAssessmentRequest(BaseModel):
    project_id: str
    num_questions: int = 3


class EvaluateAnswerRequest(BaseModel):
    project_id: str
    question: str
    answer: str
    concept: str


# -----------------------------
# Project Authorization
# -----------------------------

def verify_project(
    project_id: str,
    db: Session,
    user
):
    project = (
        db.query(Project)
        .join(Space, Project.space_id == Space.id)
        .filter(
            Project.id == project_id,
            Space.user_id == user.id
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project


# -----------------------------
# Get Material
# -----------------------------

def get_learning_context(db: Session, project_id: str, user_id, question: str = ""):
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS learning_context (
                id SERIAL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                key VARCHAR NOT NULL,
                value TEXT NOT NULL,
                source VARCHAR DEFAULT 'manual',
                confidence FLOAT DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, user_id, category, key)
            )
        """)); db.commit()
        words=[w.strip(".,?!:;()[]{}\"'") for w in question.lower().split() if len(w.strip(".,?!:;()[]{}\"'"))>2]
        params={"project_id":project_id,"user_id":str(user_id)}
        if words:
            cond=[]
            for i,w in enumerate(words[:6]):
                k=f"ctx_{i}"; cond.append(f"(LOWER(category) LIKE :{k} OR LOWER(key) LIKE :{k} OR LOWER(value) LIKE :{k})"); params[k]=f"%{w}%"
            q=f"SELECT category,key,value,confidence FROM learning_context WHERE project_id=:project_id AND user_id=:user_id AND ({' OR '.join(cond)}) ORDER BY confidence DESC, updated_at DESC LIMIT 8"
        else:
            q="SELECT category,key,value,confidence FROM learning_context WHERE project_id=:project_id AND user_id=:user_id ORDER BY confidence DESC, updated_at DESC LIMIT 8"
        return [dict(r) for r in db.execute(text(q),params).mappings().all()]
    except Exception as e:
        print("Learning context retrieval failed:",e); db.rollback(); return []

def format_learning_context(rows):
    if not rows: return "No additional learner context is available."
    return "\n".join(f"- {r['category']}: {r['value']}" for r in rows)

def get_material_context(
    project_id: str,
    db: Session
):
    rows = db.execute(
        text("""
            SELECT mc.content
            FROM material_chunks mc
            JOIN materials m
                ON mc.material_id = m.id
            WHERE m.project_id = :project_id
            ORDER BY mc.chunk_index
            LIMIT 20
        """),
        {"project_id": project_id}
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No processed learning material found"
        )

    return "\n\n".join(row[0] for row in rows)


# ============================================================
# GENERATE OPEN-ENDED ASSESSMENT
# ============================================================

@router.post("/generate")
def generate_assessment(
    request: GenerateAssessmentRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    verify_project(request.project_id, db, user)

    if request.num_questions < 1 or request.num_questions > 10:
        raise HTTPException(
            status_code=400,
            detail="Number of questions must be between 1 and 10"
        )

    material = get_material_context(
        request.project_id,
        db
    )

    learner_rows = get_learning_context(db, request.project_id, user.id)
    learner_context = format_learning_context(learner_rows)

    prompt = f"""
You are an AI learning assessment generator.

Create {request.num_questions} OPEN-ENDED assessment questions
based ONLY on the learning material below.

Use the learner context only to personalize difficulty, emphasis, and reinforcement.
Do not invent facts from learner context.

The questions should test:
- conceptual understanding
- explanation
- reasoning
- application where appropriate

Do NOT create multiple-choice questions.

Return ONLY valid JSON in exactly this format:

{{
  "questions": [
    {{
      "question": "Question text",
      "concept": "Main concept being tested",
      "expected_points": [
        "Important point 1",
        "Important point 2",
        "Important point 3"
      ]
    }}
  ]
}}

Learning Material:
{material}

Relevant Learner Context:
{learner_context}
"""

    try:
        client = get_gemini_client()
        model_name = "gemini-3.5-flash"
        ai_started_at = time.perf_counter()

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        log_ai_call(
            db=db,
            project_id=request.project_id,
            user_id=user.id,
            feature="assessment_generation",
            model=model_name,
            started_at=ai_started_at,
            response=response,
            status="success"
        )

        raw = response.text.strip()

        # Remove markdown fences if Gemini adds them
        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()

        data = json.loads(raw)

        if "questions" not in data:
            raise ValueError("Missing questions")

        return {
            "project_id": request.project_id,
            "questions": data["questions"],
            "context_used": bool(learner_rows)
        }

    except json.JSONDecodeError as e:
        try:
            log_ai_call(
                db=db,
                project_id=request.project_id,
                user_id=user.id,
                feature="assessment_generation",
                model="gemini-3.5-flash",
                started_at=ai_started_at,
                status="failure",
                error_message=str(e)
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="AI returned invalid assessment format"
        )

    except Exception as e:
        try:
            if "ai_started_at" in locals():
                log_ai_call(
                    db=db,
                    project_id=request.project_id,
                    user_id=user.id,
                    feature="assessment_generation",
                    model="gemini-3.5-flash",
                    started_at=ai_started_at,
                    status="failure",
                    error_message=str(e)
                )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Assessment generation failed: {str(e)}"
        )


# ============================================================
# EVALUATE OPEN-ENDED ANSWER
# ============================================================

@router.post("/evaluate")
def evaluate_answer(
    request: EvaluateAnswerRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    verify_project(request.project_id, db, user)

    if not request.answer.strip():
        raise HTTPException(
            status_code=400,
            detail="Answer cannot be empty"
        )

    material = get_material_context(
        request.project_id,
        db
    )

    learner_rows = get_learning_context(db, request.project_id, user.id, request.concept)
    learner_context = format_learning_context(learner_rows)

    prompt = f"""
You are an AI learning evaluator.

Evaluate the student's answer to the question.

Use the learning material as the evidence.

Question:
{request.question}

Student Answer:
{request.answer}

Concept:
{request.concept}

Learning Material:
{material}

Relevant Learner Context:
{learner_context}

Use learner context only to understand prior strengths/weaknesses and personalize feedback.
Do not use it as evidence for factual correctness.

Evaluate:
1. Understanding
2. Accuracy
3. Relevance
4. Important concepts covered
5. Missing concepts
6. Reasoning quality

Give a score from 0 to 100.

Return ONLY valid JSON:

{{
  "score": 0,
  "understanding": "What the student understood",
  "strengths": [
    "strength 1"
  ],
  "missing_concepts": [
    "missing concept 1"
  ],
  "feedback": "Clear constructive feedback",
  "recommendation": "What the student should study or practice next"
}}
"""

    try:
        client = get_gemini_client()
        model_name = "gemini-3.5-flash"
        ai_started_at = time.perf_counter()

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        log_ai_call(
            db=db,
            project_id=request.project_id,
            user_id=user.id,
            feature="assessment_evaluation",
            model=model_name,
            started_at=ai_started_at,
            response=response,
            status="success"
        )

        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()

        result = json.loads(raw)

        score = float(result.get("score", 0))

        # Safety bounds
        score = max(0, min(100, score))

        result["score"] = score

        # -----------------------------
        # Create tables
        # -----------------------------

        db.execute(
            text("""
                CREATE TABLE IF NOT EXISTS assessment_results (
                    id SERIAL PRIMARY KEY,
                    project_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    question TEXT NOT NULL,
                    concept VARCHAR NOT NULL,
                    answer TEXT NOT NULL,
                    score FLOAT NOT NULL,
                    feedback TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        )

        db.execute(
            text("""
                CREATE TABLE IF NOT EXISTS concept_mastery (
                    id SERIAL PRIMARY KEY,
                    project_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    concept VARCHAR NOT NULL,
                    mastery FLOAT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, user_id, concept)
                )
            """)
        )

        # -----------------------------
        # Save assessment
        # -----------------------------

        db.execute(
            text("""
                INSERT INTO assessment_results
                (
                    project_id,
                    user_id,
                    question,
                    concept,
                    answer,
                    score,
                    feedback
                )
                VALUES
                (
                    :project_id,
                    :user_id,
                    :question,
                    :concept,
                    :answer,
                    :score,
                    :feedback
                )
            """),
            {
                "project_id": request.project_id,
                "user_id": str(user.id),
                "question": request.question,
                "concept": request.concept,
                "answer": request.answer,
                "score": score,
                "feedback": result.get("feedback", "")
            }
        )

        # -----------------------------
        # Update mastery
        # -----------------------------

        existing = db.execute(
            text("""
                SELECT mastery
                FROM concept_mastery
                WHERE project_id = :project_id
                  AND user_id = :user_id
                  AND concept = :concept
            """),
            {
                "project_id": request.project_id,
                "user_id": str(user.id),
                "concept": request.concept
            }
        ).fetchone()

        if existing:
            old_mastery = float(existing[0])

            # Weighted update:
            # 70% previous mastery
            # 30% new evidence
            new_mastery = (
                old_mastery * 0.70
                + score * 0.30
            )

            db.execute(
                text("""
                    UPDATE concept_mastery
                    SET mastery = :mastery,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = :project_id
                      AND user_id = :user_id
                      AND concept = :concept
                """),
                {
                    "mastery": new_mastery,
                    "project_id": request.project_id,
                    "user_id": str(user.id),
                    "concept": request.concept
                }
            )

        else:

            db.execute(
                text("""
                    INSERT INTO concept_mastery
                    (
                        project_id,
                        user_id,
                        concept,
                        mastery
                    )
                    VALUES
                    (
                        :project_id,
                        :user_id,
                        :concept,
                        :mastery
                    )
                """),
                {
                    "project_id": request.project_id,
                    "user_id": str(user.id),
                    "concept": request.concept,
                    "mastery": score
                }
            )

        db.commit()

        return {
            "project_id": request.project_id,
            "concept": request.concept,
            "evaluation": result,
            "mastery_updated": True,
            "context_used": bool(learner_rows)
        }

    except json.JSONDecodeError as e:
        db.rollback()

        try:
            log_ai_call(
                db=db,
                project_id=request.project_id,
                user_id=user.id,
                feature="assessment_evaluation",
                model="gemini-3.5-flash",
                started_at=ai_started_at,
                status="failure",
                error_message=str(e)
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="AI returned invalid evaluation format"
        )

    except Exception as e:
        db.rollback()

        try:
            if "ai_started_at" in locals():
                log_ai_call(
                    db=db,
                    project_id=request.project_id,
                    user_id=user.id,
                    feature="assessment_evaluation",
                    model="gemini-3.5-flash",
                    started_at=ai_started_at,
                    status="failure",
                    error_message=str(e)
                )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Assessment evaluation failed: {str(e)}"
        )


# ============================================================
# GET PROJECT MASTERY
# ============================================================

@router.get("/{project_id}/mastery")
def get_mastery(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    verify_project(project_id, db, user)

    db.execute(
        text("""
            CREATE TABLE IF NOT EXISTS concept_mastery (
                id SERIAL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                concept VARCHAR NOT NULL,
                mastery FLOAT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, user_id, concept)
            )
        """)
    )

    rows = db.execute(
        text("""
            SELECT
                concept,
                mastery,
                updated_at
            FROM concept_mastery
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY mastery ASC
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id)
        }
    ).fetchall()

    db.commit()

    return {
        "project_id": project_id,
        "concepts": [
            {
                "concept": row[0],
                "mastery": round(float(row[1]), 2),
                "updated_at": row[2]
            }
            for row in rows
        ]
    }
# ============================================================
# BATCH ASSESSMENT EVALUATION
# ============================================================

class BatchAssessmentAnswer(BaseModel):
    question_index: int
    question: str
    answer: str
    concept: str


class BatchAssessmentRequest(BaseModel):
    project_id: str
    answers: list[BatchAssessmentAnswer]


@router.post("/evaluate-batch")
def evaluate_assessment_batch(
    request: BatchAssessmentRequest,
    current_user=Depends(get_current_user)
):
    # --------------------------------------------------------
    # Verify project ownership
    # --------------------------------------------------------
    db = SessionLocal()

    try:
        project = db.execute(
            text("""
                SELECT id
                FROM projects
                WHERE id = :project_id
                AND owner_id = :user_id
            """),
            {
                "project_id": request.project_id,
                "user_id": str(current_user.id)
            }
        ).fetchone()

        if not project:
            raise HTTPException(
                status_code=404,
                detail="Project not found."
            )

        if not request.answers:
            raise HTTPException(
                status_code=400,
                detail="No assessment answers provided."
            )

        # ----------------------------------------------------
        # Get material context
        # ----------------------------------------------------
        context = get_material_context(
            request.project_id,
            db
        )

        if not context:
            raise HTTPException(
                status_code=400,
                detail="No study material available."
            )

        # ----------------------------------------------------
        # Build ONE Gemini request
        # ----------------------------------------------------
        assessment_text = ""

        for item in request.answers:
            assessment_text += f"""
QUESTION {item.question_index + 1}
Question: {item.question}
Concept: {item.concept}
Student Answer: {item.answer}

"""

        learner_rows = get_learning_context(db, request.project_id, current_user.id)
        learner_context = format_learning_context(learner_rows)

        prompt = f"""
You are an expert educational assessment evaluator.

Evaluate ALL student answers below using the provided study material.

IMPORTANT:
- Evaluate every question.
- Score each answer from 0 to 100.
- Do not judge based on writing style alone.
- Focus on conceptual understanding, accuracy, relevance,
  reasoning and important concepts.
- Identify strengths.
- Identify missing concepts.
- Give useful feedback.
- Give a recommendation for improvement.

STUDY MATERIAL:
{context}

RELEVANT LEARNER CONTEXT:
{learner_context}

Use learner context only to personalize feedback and recommendations; use study material for factual grading.

STUDENT ASSESSMENT:
{assessment_text}

Return ONLY valid JSON.

Required format:

{{
  "evaluations": [
    {{
      "question_index": 0,
      "concept": "concept name",
      "score": 75,
      "understanding": "description",
      "strengths": [
        "strength 1",
        "strength 2"
      ],
      "missing_concepts": [
        "missing concept 1"
      ],
      "feedback": "specific feedback",
      "recommendation": "what the student should study next"
    }}
  ]
}}

Return exactly one evaluation for every question.
"""

        # ----------------------------------------------------
        # ONE Gemini call instead of 3 separate calls
        # ----------------------------------------------------
        model_name = "gemini-3.5-flash"
        ai_started_at = time.perf_counter()

        client = get_gemini_client()

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        log_ai_call(
            db=db,
            project_id=request.project_id,
            user_id=current_user.id,
            feature="assessment_evaluation_batch",
            model=model_name,
            started_at=ai_started_at,
            response=response,
            status="success"
        )

        raw_text = response.text.strip()

        # Remove markdown JSON fences if Gemini adds them
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "")
            raw_text = raw_text.replace("```", "")
            raw_text = raw_text.strip()

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Gemini returned invalid JSON."
            )

        evaluations = result.get("evaluations", [])

        if len(evaluations) != len(request.answers):
            raise HTTPException(
                status_code=500,
                detail="Gemini did not return evaluations for all questions."
            )

        # ----------------------------------------------------
        # Save results + update mastery
        # ----------------------------------------------------
        mastery_updates = []

        for evaluation, answer_data in zip(
            evaluations,
            request.answers
        ):
            score = float(evaluation.get("score", 0))
            concept = evaluation.get(
                "concept",
                answer_data.concept
            )

            # Save assessment result
            db.execute(
                text("""
                    INSERT INTO assessment_results
                    (
                        project_id,
                        user_id,
                        question,
                        answer,
                        concept,
                        score,
                        understanding,
                        strengths,
                        missing_concepts,
                        feedback,
                        recommendation
                    )
                    VALUES
                    (
                        :project_id,
                        :user_id,
                        :question,
                        :answer,
                        :concept,
                        :score,
                        :understanding,
                        :strengths,
                        :missing_concepts,
                        :feedback,
                        :recommendation
                    )
                """),
                {
                    "project_id": request.project_id,
                    "user_id": str(current_user.id),
                    "question": answer_data.question,
                    "answer": answer_data.answer,
                    "concept": concept,
                    "score": score,
                    "understanding": evaluation.get(
                        "understanding", ""
                    ),
                    "strengths": json.dumps(
                        evaluation.get("strengths", [])
                    ),
                    "missing_concepts": json.dumps(
                        evaluation.get("missing_concepts", [])
                    ),
                    "feedback": evaluation.get(
                        "feedback", ""
                    ),
                    "recommendation": evaluation.get(
                        "recommendation", ""
                    )
                }
            )

            # ----------------------------------------------
            # Existing mastery
            # ----------------------------------------------
            existing = db.execute(
                text("""
                    SELECT mastery
                    FROM concept_mastery
                    WHERE project_id = :project_id
                    AND user_id = :user_id
                    AND concept = :concept
                """),
                {
                    "project_id": request.project_id,
                    "user_id": str(current_user.id),
                    "concept": concept
                }
            ).fetchone()

            if existing:
                old_mastery = float(existing[0])

                new_mastery = (
                    old_mastery * 0.70
                    + score * 0.30
                )

                db.execute(
                    text("""
                        UPDATE concept_mastery
                        SET mastery = :mastery,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE project_id = :project_id
                        AND user_id = :user_id
                        AND concept = :concept
                    """),
                    {
                        "mastery": new_mastery,
                        "project_id": request.project_id,
                        "user_id": str(current_user.id),
                        "concept": concept
                    }
                )

            else:
                db.execute(
                    text("""
                        INSERT INTO concept_mastery
                        (
                            project_id,
                            user_id,
                            concept,
                            mastery
                        )
                        VALUES
                        (
                            :project_id,
                            :user_id,
                            :concept,
                            :mastery
                        )
                    """),
                    {
                        "project_id": request.project_id,
                        "user_id": str(current_user.id),
                        "concept": concept,
                        "mastery": score
                    }
                )

            mastery_updates.append({
                "concept": concept,
                "score": score
            })

        db.commit()

        return {
            "success": True,
            "evaluations": evaluations,
            "mastery_updated": mastery_updates,
            "context_used": bool(learner_rows)
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        print("Batch assessment error:", str(e))

        try:
            if "ai_started_at" in locals():
                log_ai_call(
                    db=db,
                    project_id=request.project_id,
                    user_id=current_user.id,
                    feature="assessment_evaluation_batch",
                    model="gemini-3.5-flash",
                    started_at=ai_started_at,
                    status="failure",
                    error_message=str(e)
                )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Assessment evaluation failed: {str(e)}"
        )

    finally:
        db.close()