from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .models import Project, Space
from .workspace_routes import get_current_user

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


def verify_project(
    project_id: str,
    db: Session,
    user
):
    project = (
        db.query(Project)
        .join(
            Space,
            Project.space_id == Space.id
        )
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


@router.get("/{project_id}")
def get_project_analytics(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(
        project_id,
        db,
        user
    )

    # Activity statistics
    activity_rows = db.execute(
        text("""
            SELECT
                event_type,
                COUNT(*) AS count
            FROM activity_events
            WHERE project_id = :project_id
            AND user_id = :user_id
            GROUP BY event_type
            ORDER BY count DESC
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).fetchall()

    activity = [
        {
            "event_type": row.event_type,
            "count": row.count
        }
        for row in activity_rows
    ]

    # Quiz statistics
    quiz_row = db.execute(
        text("""
            SELECT
                COUNT(*) AS attempts,
                COALESCE(AVG(percentage), 0) AS average_percentage,
                COALESCE(MAX(percentage), 0) AS best_percentage
            FROM quiz_results
            WHERE project_id = :project_id
            AND user_id = :user_id
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).fetchone()

    quiz = {
        "attempts": quiz_row.attempts or 0,
        "average_percentage": round(
            float(
                quiz_row.average_percentage or 0
            ),
            2
        ),
        "best_percentage": round(
            float(
                quiz_row.best_percentage or 0
            ),
            2
        )
    }

    # Assessment statistics
    assessment_row = db.execute(
        text("""
            SELECT
                COUNT(*) AS attempts,
                COALESCE(AVG(score), 0) AS average_score
            FROM assessment_results
            WHERE project_id = :project_id
        """),
        {
            "project_id": project_id
        }
    ).fetchone()

    assessment = {
        "attempts": assessment_row.attempts or 0,
        "average_score": round(
            float(
                assessment_row.average_score or 0
            ),
            2
        )
    }

    # Concept mastery
    mastery_rows = db.execute(
        text("""
            SELECT
                concept,
                mastery
            FROM concept_mastery
            WHERE project_id = :project_id
            ORDER BY mastery DESC
        """),
        {
            "project_id": project_id
        }
    ).fetchall()

    mastery = [
        {
            "concept": row.concept,
            "mastery": round(
                float(row.mastery),
                2
            )
        }
        for row in mastery_rows
    ]

    # AI activity
    tutor_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM activity_events
            WHERE project_id = :project_id
            AND user_id = :user_id
            AND event_type = 'TUTOR_ASKED'
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).scalar() or 0

    quiz_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM activity_events
            WHERE project_id = :project_id
            AND user_id = :user_id
            AND event_type = 'QUIZ_GENERATED'
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).scalar() or 0

    ai_activity = {
        "tutor_questions": tutor_count,
        "quizzes_generated": quiz_count
    }

    return {
        "project_id": project_id,
        "activity": activity,
        "quiz": quiz,
        "assessment": assessment,
        "mastery": mastery,
        "ai_activity": ai_activity
    }