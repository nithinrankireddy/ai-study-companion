import os
import json
import time

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from google import genai

from .database import get_db
from .models import Project, Space
from .workspace_routes import get_current_user
from .ai_observability import log_ai_call


load_dotenv()


router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class QuizRequest(BaseModel):
    project_id: str
    num_questions: int = 5


# ============================================================
# MATERIAL CONTEXT
# ============================================================

def get_material_context(project_id: str, db: Session):
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
        {
            "project_id": project_id
        }
    ).fetchall()

    return "\n\n".join(
        row[0]
        for row in rows
    )


# ============================================================
# PREVIOUS QUIZ PERFORMANCE
# ============================================================

def get_quiz_history(
    project_id: str,
    user_id,
    db: Session
):
    rows = db.execute(
        text("""
            SELECT
                score,
                total,
                percentage,
                created_at
            FROM quiz_results
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 10
        """),
        {
            "project_id": project_id,
            "user_id": str(user_id)
        }
    ).fetchall()

    history = []

    for row in rows:
        history.append({
            "score": row[0],
            "total": row[1],
            "percentage": float(row[2]),
            "created_at": str(row[3])
        })

    return history


# ============================================================
# LEARNING ACTIVITY
# ============================================================

def get_learning_activity(
    project_id: str,
    user_id,
    db: Session
):
    rows = db.execute(
        text("""
            SELECT
                event_type,
                metadata,
                created_at
            FROM activity_events
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 20
        """),
        {
            "project_id": project_id,
            "user_id": str(user_id)
        }
    ).fetchall()

    activity = []

    for row in rows:
        metadata = row[1]

        if metadata is None:
            metadata = {}

        activity.append({
            "event_type": row[0],
            "metadata": metadata,
            "created_at": str(row[2])
        })

    return activity


# ============================================================
# PERSISTENT LEARNING CONTEXT
# ============================================================

def get_learning_context(project_id: str, user_id, db: Session):
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
        """))
        db.commit()

        rows = db.execute(text("""
            SELECT category, key, value, confidence
            FROM learning_context
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY confidence DESC, updated_at DESC
            LIMIT 10
        """), {
            'project_id': project_id,
            'user_id': str(user_id)
        }).mappings().all()

        return [dict(row) for row in rows]
    except Exception as e:
        print('Learning context could not be loaded:', str(e))
        db.rollback()
        return []


def format_learning_context(rows):
    if not rows:
        return 'No additional persistent learner context is available.'
    return '\n'.join(
        f"- {row['category']}: {row['value']}"
        for row in rows
    )


# ============================================================
# DETERMINE DIFFICULTY
# ============================================================

def determine_difficulty(history):
    if not history:
        return "medium"

    average = sum(
        item["percentage"]
        for item in history
    ) / len(history)

    latest = history[0]["percentage"]

    # Weak recent performance
    if latest < 40 or average < 45:
        return "easy_to_medium"

    # Moderate performance
    if latest < 70 or average < 70:
        return "medium"

    # Strong performance
    return "medium_to_hard"


# ============================================================
# GENERATE ADAPTIVE QUIZ
# ============================================================

@router.post("/generate")
def generate_quiz(
    request: QuizRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    # --------------------------------------------------------
    # Validate number of questions
    # --------------------------------------------------------

    if request.num_questions < 1:
        raise HTTPException(
            status_code=400,
            detail="Number of questions must be at least 1."
        )

    if request.num_questions > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 questions allowed."
        )

    # --------------------------------------------------------
    # Verify project ownership
    # --------------------------------------------------------

    project = (
        db.query(Project)
        .join(
            Space,
            Project.space_id == Space.id
        )
        .filter(
            Project.id == request.project_id,
            Space.user_id == user.id
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    # --------------------------------------------------------
    # Study material
    # --------------------------------------------------------

    context = get_material_context(
        request.project_id,
        db
    )

    if not context:
        raise HTTPException(
            status_code=404,
            detail="No processed study material found"
        )

    # --------------------------------------------------------
    # Previous performance
    # --------------------------------------------------------

    try:
        history = get_quiz_history(
            request.project_id,
            user.id,
            db
        )
    except Exception as e:
        print(
            "Quiz history could not be loaded:",
            str(e)
        )
        history = []

    # --------------------------------------------------------
    # Activity history
    # --------------------------------------------------------

    try:
        activity = get_learning_activity(
            request.project_id,
            user.id,
            db
        )
    except Exception as e:
        print(
            "Activity history could not be loaded:",
            str(e)
        )
        activity = []

    # --------------------------------------------------------
    # Persistent learning context
    # --------------------------------------------------------

    learner_context = get_learning_context(
        request.project_id,
        user.id,
        db
    )

    learner_context_text = format_learning_context(
        learner_context
    )

    # --------------------------------------------------------
    # Adaptive difficulty
    # --------------------------------------------------------

    difficulty = determine_difficulty(
        history
    )

    # --------------------------------------------------------
    # Performance summary
    # --------------------------------------------------------

    if history:

        average_score = sum(
            item["percentage"]
            for item in history
        ) / len(history)

        latest_score = history[0]["percentage"]

        best_score = max(
            item["percentage"]
            for item in history
        )

    else:

        average_score = 0
        latest_score = 0
        best_score = 0

    # --------------------------------------------------------
    # Format history for AI
    # --------------------------------------------------------

    history_text = "No previous quiz attempts."

    if history:

        history_text = json.dumps(
            history,
            indent=2
        )

    # --------------------------------------------------------
    # Format activity for AI
    # --------------------------------------------------------

    activity_text = "No recent learning activity."

    if activity:

        activity_text = json.dumps(
            activity,
            indent=2
        )

    # --------------------------------------------------------
    # Gemini API key
    # --------------------------------------------------------

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY not configured"
        )

    # --------------------------------------------------------
    # Gemini
    # --------------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

        prompt = f"""
You are an adaptive AI learning assessment system.

Your job is to generate a personalized multiple-choice quiz
from the student's study material.

IMPORTANT:
This is NOT a generic quiz.

Use the student's previous performance and learning activity
to adapt the quiz.

============================================================
STUDENT PERFORMANCE
============================================================

Previous quiz attempts:

{history_text}

Average score:
{average_score:.1f}%

Latest score:
{latest_score:.1f}%

Best score:
{best_score:.1f}%

Recommended difficulty:
{difficulty}

============================================================
RECENT LEARNING ACTIVITY
============================================================

{activity_text}

============================================================
PERSISTENT LEARNER CONTEXT
============================================================

{learner_context_text}

Use this context only to personalize the quiz: reinforce weak areas,
respect learning needs, and vary examples when appropriate.
Do not invent facts from this context that are not supported by the study material.

============================================================
ADAPTIVE RULES
============================================================

If the student has weak recent performance:
- Use easier-to-medium questions.
- Focus on foundational concepts.
- Test concepts that appear important in the material.
- Avoid making every question extremely difficult.

If the student has moderate performance:
- Use medium difficulty.
- Mix conceptual and application questions.
- Gradually increase difficulty.

If the student has strong performance:
- Use medium-to-hard questions.
- Include application and reasoning questions.
- Include challenging conceptual questions.

The quiz should help the student learn, not simply test
memorization.

============================================================
STUDY MATERIAL
============================================================

{context}

============================================================
QUIZ REQUIREMENTS
============================================================

Generate exactly {request.num_questions} questions.

Each question must have:

- question
- exactly 4 options
- one correct answer
- short explanation
- difficulty
- concept

Return ONLY valid JSON.

Required format:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": 0,
      "explanation": "Short explanation",
      "difficulty": "medium",
      "concept": "Concept being tested"
    }}
  ]
}}

Rules:

1. The "answer" must be a zero-based option index.
2. Every question must have exactly 4 options.
3. Only one option should be correct.
4. Questions must be based on the provided study material.
5. Do not invent concepts that are not supported by the material.
6. Avoid duplicate questions.
7. Mix conceptual and application-based questions.
8. Adapt difficulty using the student's performance.
9. Return exactly {request.num_questions} questions.
10. Return JSON only.
"""

        ai_started_at = time.perf_counter()

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        log_ai_call(
            db=db,
            project_id=request.project_id,
            user_id=user.id,
            feature="adaptive_quiz",
            model="gemini-3.5-flash",
            started_at=ai_started_at,
            response=response,
            status="success"
        )

        raw_text = response.text.strip()

        # ----------------------------------------------------
        # Remove markdown JSON fences
        # ----------------------------------------------------

        if raw_text.startswith("```"):

            raw_text = raw_text.replace(
                "```json",
                ""
            )

            raw_text = raw_text.replace(
                "```",
                ""
            )

            raw_text = raw_text.strip()

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        quiz = json.loads(
            raw_text
        )

        questions = quiz.get(
            "questions",
            []
        )

        # ----------------------------------------------------
        # Validate generated quiz
        # ----------------------------------------------------

        if len(questions) != request.num_questions:

            raise HTTPException(
                status_code=500,
                detail=(
                    "AI did not generate the requested "
                    "number of questions."
                )
            )

        validated_questions = []

        for question in questions:

            options = question.get(
                "options",
                []
            )

            if len(options) != 4:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "AI generated a question "
                        "without exactly 4 options."
                    )
                )

            answer = question.get(
                "answer"
            )

            if not isinstance(
                answer,
                int
            ) or answer < 0 or answer > 3:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "AI generated an invalid "
                        "answer index."
                    )
                )

            validated_questions.append({
                "question": question.get(
                    "question",
                    ""
                ),
                "options": options,
                "answer": answer,
                "explanation": question.get(
                    "explanation",
                    ""
                ),
                "difficulty": question.get(
                    "difficulty",
                    difficulty
                ),
                "concept": question.get(
                    "concept",
                    "General"
                )
            })

        # ----------------------------------------------------
        # Return adaptive quiz
        # ----------------------------------------------------

        return {
            "project_id": request.project_id,
            "questions": validated_questions,
            "adaptive": True,
            "difficulty": difficulty,
            "history_used": len(history),
            "average_score": round(
                average_score,
                2
            ),
            "latest_score": round(
                latest_score,
                2
            ),
            "best_score": round(
                best_score,
                2
            ),
            "context_used": bool(learner_context)
        }

    # --------------------------------------------------------
    # Invalid JSON
    # --------------------------------------------------------

    except json.JSONDecodeError as e:

        try:
            log_ai_call(
                db=db,
                project_id=request.project_id,
                user_id=user.id,
                feature="adaptive_quiz",
                model="gemini-3.5-flash",
                started_at=ai_started_at,
                status="failure",
                error_message=str(e)
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="AI returned invalid quiz format"
        )

    # --------------------------------------------------------
    # Gemini quota / API errors
    # --------------------------------------------------------

    except Exception as e:

        error_message = str(e)

        print(
            "Quiz generation error:",
            error_message
        )

        try:
            if "ai_started_at" in locals():
                log_ai_call(
                    db=db,
                    project_id=request.project_id,
                    user_id=user.id,
                    feature="adaptive_quiz",
                    model="gemini-3.5-flash",
                    started_at=ai_started_at,
                    status="failure",
                    error_message=error_message
                )
        except Exception:
            pass

        if (
            "429" in error_message
            or
            "RESOURCE_EXHAUSTED"
            in error_message
        ):

            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini API quota is currently "
                    "exhausted. Please wait and try "
                    "again later."
                )
            )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Quiz generation error: "
                f"{error_message}"
            )
        )