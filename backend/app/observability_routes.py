import time
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user


router = APIRouter(
    prefix="/observability",
    tags=["AI Observability"]
)


# ============================================================
# TABLE
# ============================================================

def ensure_table(db: Session):

    db.execute(
        text("""
            CREATE TABLE IF NOT EXISTS ai_observability (
                id SERIAL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                feature VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                latency_ms FLOAT DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost FLOAT DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    )

    db.commit()


# ============================================================
# REQUEST
# ============================================================

class AIObservabilityRequest(BaseModel):
    project_id: str
    feature: str
    model: str
    status: str
    latency_ms: float = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0
    error_message: str = ""


# ============================================================
# LOG AI REQUEST
# ============================================================

@router.post("/log")
def log_ai_request(
    request: AIObservabilityRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    ensure_table(db)

    db.execute(
        text("""
            INSERT INTO ai_observability (
                project_id,
                user_id,
                feature,
                model,
                status,
                latency_ms,
                prompt_tokens,
                output_tokens,
                total_tokens,
                estimated_cost,
                error_message
            )
            VALUES (
                :project_id,
                :user_id,
                :feature,
                :model,
                :status,
                :latency_ms,
                :prompt_tokens,
                :output_tokens,
                :total_tokens,
                :estimated_cost,
                :error_message
            )
        """),
        {
            "project_id": request.project_id,
            "user_id": str(user.id),
            "feature": request.feature,
            "model": request.model,
            "status": request.status,
            "latency_ms": request.latency_ms,
            "prompt_tokens": request.prompt_tokens,
            "output_tokens": request.output_tokens,
            "total_tokens": request.total_tokens,
            "estimated_cost": request.estimated_cost,
            "error_message": request.error_message
        }
    )

    db.commit()

    return {
        "success": True,
        "message": "AI observability event recorded"
    }


# ============================================================
# PROJECT ANALYTICS
# ============================================================

@router.get("/{project_id}")
def get_observability(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    ensure_table(db)

    rows = db.execute(
        text("""
            SELECT
                feature,
                model,
                status,
                COUNT(*) AS requests,
                ROUND(
                    AVG(latency_ms)::numeric,
                    2
                ) AS avg_latency_ms,
                SUM(prompt_tokens) AS prompt_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(estimated_cost) AS estimated_cost
            FROM ai_observability
            WHERE project_id = :project_id
              AND user_id = :user_id
            GROUP BY feature, model, status
            ORDER BY requests DESC
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id)
        }
    ).fetchall()

    records = []

    for row in rows:
        records.append({
            "feature": row[0],
            "model": row[1],
            "status": row[2],
            "requests": row[3],
            "avg_latency_ms": float(row[4] or 0),
            "prompt_tokens": row[5] or 0,
            "output_tokens": row[6] or 0,
            "total_tokens": row[7] or 0,
            "estimated_cost": float(row[8] or 0)
        })

    return {
        "project_id": project_id,
        "records": records
    }


# ============================================================
# GLOBAL SUMMARY
# ============================================================

@router.get("/{project_id}/summary")
def get_observability_summary(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    ensure_table(db)

    result = db.execute(
        text("""
            SELECT
                COUNT(*) AS total_requests,

                COUNT(*) FILTER (
                    WHERE status = 'success'
                ) AS successful_requests,

                COUNT(*) FILTER (
                    WHERE status = 'failure'
                ) AS failed_requests,

                COALESCE(
                    AVG(latency_ms),
                    0
                ) AS avg_latency,

                COALESCE(
                    SUM(total_tokens),
                    0
                ) AS total_tokens,

                COALESCE(
                    SUM(estimated_cost),
                    0
                ) AS total_cost

            FROM ai_observability

            WHERE project_id = :project_id
              AND user_id = :user_id
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id)
        }
    ).fetchone()

    return {
        "total_requests": result[0] or 0,
        "successful_requests": result[1] or 0,
        "failed_requests": result[2] or 0,
        "average_latency_ms": round(
            float(result[3] or 0),
            2
        ),
        "total_tokens": result[4] or 0,
        "estimated_cost": round(
            float(result[5] or 0),
            6
        )
    }