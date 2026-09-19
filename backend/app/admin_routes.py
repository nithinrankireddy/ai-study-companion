import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user


router = APIRouter(
    prefix="/admin",
    tags=["Admin Dashboard"]
)


# ============================================================
# ADMIN AUTHORIZATION
# ============================================================

def get_admin_user(user=Depends(get_current_user)):
    if getattr(user, "role", "user") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user


# ============================================================
# SAFE QUERY HELPERS
# ============================================================

def safe_scalar(db: Session, query: str, default=0):
    try:
        value = db.execute(text(query)).scalar()
        return value if value is not None else default
    except Exception as e:
        db.rollback()
        print("Admin query failed:", e)
        return default


def safe_rows(db: Session, query: str):
    try:
        return db.execute(text(query)).mappings().all()
    except Exception as e:
        db.rollback()
        print("Admin query failed:", e)
        return []


# ============================================================
# ADMIN OVERVIEW
# ============================================================

@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    users = safe_scalar(
        db,
        "SELECT COUNT(*) FROM users"
    )

    spaces = safe_scalar(
        db,
        "SELECT COUNT(*) FROM spaces"
    )

    projects = safe_scalar(
        db,
        "SELECT COUNT(*) FROM projects"
    )

    materials = safe_scalar(
        db,
        "SELECT COUNT(*) FROM materials"
    )

    processed_materials = safe_scalar(
        db,
        """
        SELECT COUNT(*)
        FROM materials
        WHERE status = 'processed'
        """
    )

    quiz_attempts = safe_scalar(
        db,
        "SELECT COUNT(*) FROM quiz_results"
    )

    average_quiz_score = safe_scalar(
        db,
        """
        SELECT COALESCE(AVG(percentage), 0)
        FROM quiz_results
        """,
        0
    )

    assessment_attempts = safe_scalar(
        db,
        "SELECT COUNT(*) FROM assessment_results"
    )

    average_assessment_score = safe_scalar(
        db,
        """
        SELECT COALESCE(AVG(score), 0)
        FROM assessment_results
        """,
        0
    )

    tutor_questions = safe_scalar(
        db,
        """
        SELECT COUNT(*)
        FROM activity_events
        WHERE event_type = 'TUTOR_ASKED'
        """
    )

    ai_requests = safe_scalar(
        db,
        "SELECT COUNT(*) FROM ai_observability"
    )

    ai_successes = safe_scalar(
        db,
        """
        SELECT COUNT(*)
        FROM ai_observability
        WHERE status = 'success'
        """
    )

    ai_failures = safe_scalar(
        db,
        """
        SELECT COUNT(*)
        FROM ai_observability
        WHERE status = 'failure'
        """
    )

    total_tokens = safe_scalar(
        db,
        """
        SELECT COALESCE(SUM(total_tokens), 0)
        FROM ai_observability
        """
    )

    estimated_cost = safe_scalar(
        db,
        """
        SELECT COALESCE(SUM(estimated_cost), 0)
        FROM ai_observability
        """,
        0
    )

    average_latency = safe_scalar(
        db,
        """
        SELECT COALESCE(AVG(latency_ms), 0)
        FROM ai_observability
        WHERE status = 'success'
        """,
        0
    )

    return {
        "users": int(users),
        "spaces": int(spaces),
        "projects": int(projects),
        "materials": int(materials),
        "processed_materials": int(processed_materials),
        "learning": {
            "quiz_attempts": int(quiz_attempts),
            "average_quiz_score": round(float(average_quiz_score), 2),
            "assessment_attempts": int(assessment_attempts),
            "average_assessment_score": round(
                float(average_assessment_score),
                2
            ),
            "tutor_questions": int(tutor_questions),
        },
        "ai": {
            "requests": int(ai_requests),
            "successes": int(ai_successes),
            "failures": int(ai_failures),
            "success_rate": round(
                (
                    (float(ai_successes) / float(ai_requests)) * 100
                    if ai_requests
                    else 0
                ),
                2
            ),
            "total_tokens": int(total_tokens),
            "estimated_cost": round(float(estimated_cost), 6),
            "average_latency_ms": round(
                float(average_latency),
                2
            ),
        }
    }


# ============================================================
# USERS
# ============================================================

@router.get("/users")
def admin_users(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    rows = safe_rows(
        db,
        """
        SELECT
            id,
            name,
            email,
            role,
            created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT 100
        """
    )

    return {
        "users": [dict(row) for row in rows]
    }


# ============================================================
# PROJECTS
# ============================================================

@router.get("/projects")
def admin_projects(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    rows = safe_rows(
        db,
        """
        SELECT
            p.id,
            p.name,
            p.created_at,
            s.name AS space_name,
            u.email AS owner_email
        FROM projects p
        JOIN spaces s
            ON s.id = p.space_id
        JOIN users u
            ON u.id = s.user_id
        ORDER BY p.created_at DESC
        LIMIT 100
        """
    )

    return {
        "projects": [dict(row) for row in rows]
    }


# ============================================================
# ACTIVITY
# ============================================================

@router.get("/activity")
def admin_activity(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    rows = safe_rows(
        db,
        """
        SELECT
            ae.id,
            ae.project_id,
            ae.user_id,
            ae.event_type,
            ae.metadata,
            ae.created_at
        FROM activity_events ae
        ORDER BY ae.created_at DESC
        LIMIT 100
        """
    )

    return {
        "activity": [dict(row) for row in rows]
    }


# ============================================================
# AI USAGE
# ============================================================

@router.get("/ai-usage")
def admin_ai_usage(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    rows = safe_rows(
        db,
        """
        SELECT
            feature,
            model,
            status,
            COUNT(*) AS requests,
            COALESCE(AVG(latency_ms), 0) AS average_latency_ms,
            COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(estimated_cost), 0) AS estimated_cost
        FROM ai_observability
        GROUP BY feature, model, status
        ORDER BY requests DESC
        """
    )

    return {
        "ai_usage": [dict(row) for row in rows]
    }


# ============================================================
# SYSTEM HEALTH
# ============================================================

@router.get("/health")
def admin_health(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user)
):
    database_ok = True

    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        database_ok = False
        db.rollback()
        print("Database health check failed:", e)

    return {
        "status": "healthy" if database_ok else "degraded",
        "database": "connected" if database_ok else "error",
        "api": "running"
    }
