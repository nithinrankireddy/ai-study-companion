import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user

router = APIRouter(prefix="/evaluation", tags=["AI Evaluation"])


class TutorEvaluationRequest(BaseModel):
    project_id: str
    question: str
    answer: str
    sources: list[str] = []


class RetrievalEvaluationRequest(BaseModel):
    project_id: str
    query: str
    retrieved_chunks: list[str] = []


class AssessmentEvaluationRequest(BaseModel):
    project_id: str
    question: str
    student_answer: str
    evaluation: dict


class RecommendationEvaluationRequest(BaseModel):
    project_id: str
    recommendation: str
    learner_context: list[str] = []


def verify_project(db: Session, project_id: str, user_id):
    row = db.execute(
        text("""
            SELECT p.id
            FROM projects p
            JOIN spaces s ON s.id = p.space_id
            WHERE p.id = :project_id
              AND s.user_id = :user_id
        """),
        {"project_id": project_id, "user_id": str(user_id)}
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")


def ensure_table(db: Session):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS ai_evaluations (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            feature VARCHAR NOT NULL,
            score FLOAT NOT NULL,
            passed BOOLEAN NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.commit()


def tokenize(value: str):
    return set(
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9_]+", value or "")
        if len(word) > 2
    )


def overlap_score(a: str, b: str):
    left = tokenize(a)
    right = tokenize(b)

    if not left or not right:
        return 0.0

    return round((len(left & right) / len(left)) * 100, 2)


def save_evaluation(db, project_id, user_id, feature, score, passed, details):
    ensure_table(db)

    db.execute(
        text("""
            INSERT INTO ai_evaluations
            (project_id, user_id, feature, score, passed, details)
            VALUES
            (:project_id, :user_id, :feature, :score, :passed, CAST(:details AS JSONB))
        """),
        {
            "project_id": project_id,
            "user_id": str(user_id),
            "feature": feature,
            "score": score,
            "passed": passed,
            "details": __import__("json").dumps(details),
        }
    )
    db.commit()


@router.post("/tutor")
def evaluate_tutor(
    request: TutorEvaluationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, request.project_id, user.id)

    source_text = "\n".join(request.sources)
    groundedness = overlap_score(request.answer, source_text)

    has_sources = len(request.sources) > 0
    has_answer = bool(request.answer.strip())
    unsupported_handling = (
        "not found" in request.answer.lower()
        or "not available" in request.answer.lower()
        or groundedness >= 10
    )

    score = round(
        groundedness * 0.7
        + (20 if has_sources else 0)
        + (10 if has_answer else 0),
        2
    )
    score = min(score, 100.0)
    passed = score >= 50 and has_answer

    details = {
        "groundedness_overlap": groundedness,
        "citation_present": has_sources,
        "answer_present": has_answer,
        "unsupported_handling_signal": unsupported_handling,
    }

    save_evaluation(
        db, request.project_id, user.id,
        "tutor_groundedness", score, passed, details
    )

    return {
        "feature": "tutor_groundedness",
        "score": score,
        "passed": passed,
        "details": details,
    }


@router.post("/retrieval")
def evaluate_retrieval(
    request: RetrievalEvaluationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, request.project_id, user.id)

    if not request.retrieved_chunks:
        score = 0.0
    else:
        scores = [
            overlap_score(request.query, chunk)
            for chunk in request.retrieved_chunks
        ]
        score = round(max(scores), 2)

    passed = score >= 10

    details = {
        "query": request.query,
        "chunks_checked": len(request.retrieved_chunks),
        "best_relevance_score": score,
    }

    save_evaluation(
        db, request.project_id, user.id,
        "retrieval_relevance", score, passed, details
    )

    return {
        "feature": "retrieval_relevance",
        "score": score,
        "passed": passed,
        "details": details,
    }


@router.post("/assessment")
def evaluate_assessment_quality(
    request: AssessmentEvaluationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, request.project_id, user.id)

    evaluation = request.evaluation or {}

    score_value = evaluation.get("score", 0)
    try:
        score_value = float(score_value)
    except (TypeError, ValueError):
        score_value = 0

    score_value = max(0.0, min(100.0, score_value))

    required_fields = [
        "understanding",
        "feedback",
        "recommendation",
    ]
    present = sum(
        1 for field in required_fields
        if str(evaluation.get(field, "")).strip()
    )

    structure_score = (present / len(required_fields)) * 100
    final_score = round(
        score_value * 0.6 + structure_score * 0.4,
        2
    )
    passed = present == len(required_fields)

    details = {
        "grading_score": score_value,
        "required_feedback_fields_present": present,
        "required_feedback_fields": required_fields,
        "structure_score": round(structure_score, 2),
    }

    save_evaluation(
        db, request.project_id, user.id,
        "assessment_quality", final_score, passed, details
    )

    return {
        "feature": "assessment_quality",
        "score": final_score,
        "passed": passed,
        "details": details,
    }


@router.post("/recommendation")
def evaluate_recommendation(
    request: RecommendationEvaluationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, request.project_id, user.id)

    has_recommendation = bool(request.recommendation.strip())
    context_text = "\n".join(request.learner_context)

    relevance = overlap_score(
        request.recommendation,
        context_text
    ) if context_text else 0.0

    action_words = {
        "study", "practice", "review", "learn",
        "complete", "focus", "revise", "attempt"
    }
    recommendation_words = tokenize(request.recommendation)
    actionable = bool(recommendation_words & action_words)

    score = min(
        100.0,
        round(
            relevance * 0.7
            + (30 if actionable else 0)
            if context_text
            else (70 if actionable else 20),
            2
        )
    )

    passed = has_recommendation and actionable

    details = {
        "context_relevance": relevance,
        "actionable": actionable,
        "context_items": len(request.learner_context),
    }

    save_evaluation(
        db, request.project_id, user.id,
        "recommendation_quality", score, passed, details
    )

    return {
        "feature": "recommendation_quality",
        "score": score,
        "passed": passed,
        "details": details,
    }


@router.get("/{project_id}")
def get_evaluations(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, project_id, user.id)
    ensure_table(db)

    rows = db.execute(
        text("""
            SELECT
                id,
                feature,
                score,
                passed,
                details,
                created_at
            FROM ai_evaluations
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id),
        }
    ).mappings().all()

    return {
        "project_id": project_id,
        "count": len(rows),
        "evaluations": [dict(row) for row in rows],
    }


@router.get("/{project_id}/summary")
def get_evaluation_summary(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(db, project_id, user.id)
    ensure_table(db)

    rows = db.execute(
        text("""
            SELECT
                feature,
                COUNT(*) AS evaluations,
                ROUND(AVG(score)::numeric, 2) AS average_score,
                SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS failed
            FROM ai_evaluations
            WHERE project_id = :project_id
              AND user_id = :user_id
            GROUP BY feature
            ORDER BY feature
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id),
        }
    ).mappings().all()

    return {
        "project_id": project_id,
        "summary": [dict(row) for row in rows],
    }
