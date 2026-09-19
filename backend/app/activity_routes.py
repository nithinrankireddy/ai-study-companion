from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .models import Project, Space
from .workspace_routes import get_current_user

router = APIRouter(
    prefix="/activity",
    tags=["Activity Tracking"]
)


class ActivityRequest(BaseModel):
    project_id: str
    event_type: str
    metadata: dict = {}


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


def ensure_table(db: Session):
    db.execute(
        text("""
            CREATE TABLE IF NOT EXISTS activity_events (
                id SERIAL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    )

    db.commit()


@router.post("/event")
def create_activity(
    request: ActivityRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(
        request.project_id,
        db,
        user
    )

    if not request.event_type.strip():
        raise HTTPException(
            status_code=400,
            detail="event_type is required"
        )

    ensure_table(db)

    db.execute(
        text("""
            INSERT INTO activity_events
            (
                project_id,
                user_id,
                event_type,
                metadata
            )
            VALUES
            (
                :project_id,
                :user_id,
                :event_type,
                CAST(:metadata AS JSONB)
            )
        """),
        {
            "project_id": request.project_id,
            "user_id": user.id,
            "event_type": request.event_type,
            "metadata": str(request.metadata).replace(
                "'",
                '"'
            )
        }
    )

    db.commit()

    return {
        "status": "recorded",
        "event_type": request.event_type
    }


@router.get("/{project_id}")
def get_project_activity(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(
        project_id,
        db,
        user
    )

    ensure_table(db)

    rows = db.execute(
        text("""
            SELECT
                id,
                event_type,
                metadata,
                created_at
            FROM activity_events
            WHERE project_id = :project_id
            AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {
            "project_id": project_id,
            "user_id": user.id
        }
    ).fetchall()

    return {
        "project_id": project_id,
        "events": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "metadata": row.metadata,
                "created_at": str(
                    row.created_at
                )
            }
            for row in rows
        ]
    }