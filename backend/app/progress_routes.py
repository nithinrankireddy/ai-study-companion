from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .models import Project, Space
from .workspace_routes import get_current_user

router = APIRouter(
    prefix="/progress",
    tags=["Progress"]
)


class ProgressRequest(BaseModel):
    project_id: str
    score: int
    total: int


def ensure_table(db: Session):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.commit()


@router.post("/quiz")
def save_quiz_result(
    request: ProgressRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ensure_table(db)

    project = (
        db.query(Project)
        .join(Space, Project.space_id == Space.id)
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

    percentage = (
        request.score / request.total * 100
        if request.total > 0 else 0
    )

    db.execute(
        text("""
            INSERT INTO quiz_results
            (project_id, user_id, score, total, percentage)
            VALUES
            (:project_id, :user_id, :score, :total, :percentage)
        """),
        {
            "project_id": request.project_id,
            "user_id": user.id,
            "score": request.score,
            "total": request.total,
            "percentage": percentage
        }
    )

    db.commit()

    return {
        "message": "Quiz result saved",
        "score": request.score,
        "total": request.total,
        "percentage": percentage
    }


@router.get("/{project_id}")
def get_progress(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ensure_table(db)

    results = db.execute(
        text("""
            SELECT score, total, percentage, created_at
            FROM quiz_results
            WHERE project_id = :project_id
            AND user_id = :user_id
            ORDER BY created_at DESC
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).fetchall()

    return {
        "results": [
            {
                "score": row[0],
                "total": row[1],
                "percentage": row[2],
                "created_at": row[3]
            }
            for row in results
        ]
    }