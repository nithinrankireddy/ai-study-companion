import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db, SessionLocal
from .workspace_routes import get_current_user

router = APIRouter(prefix="/workflow", tags=["Learning Workflows"])


class WorkflowRequest(BaseModel):
    project_id: str
    trigger: str = "manual"


def ensure_tables(db: Session):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS learning_workflows (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            workflow_type VARCHAR NOT NULL,
            trigger VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'queued',
            result JSONB,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS learning_recommendations (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            recommendation TEXT NOT NULL,
            reason TEXT,
            priority VARCHAR DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.commit()


def verify_project(db, project_id, user_id):
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


def process_learning_workflow(workflow_id: int, project_id: str, user_id: str):
    db = SessionLocal()

    try:
        ensure_tables(db)

        db.execute(
            text("""
                UPDATE learning_workflows
                SET status = 'running',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {"id": workflow_id}
        )
        db.commit()

        # --------------------------------------------------
        # 1. Read latest learning evidence
        # --------------------------------------------------
        quiz = db.execute(
            text("""
                SELECT
                    COUNT(*) AS attempts,
                    COALESCE(AVG(percentage), 0) AS average,
                    COALESCE(MAX(percentage), 0) AS best
                FROM quiz_results
                WHERE project_id = :project_id
                  AND user_id = :user_id
            """),
            {"project_id": project_id, "user_id": user_id}
        ).mappings().first()

        mastery = db.execute(
            text("""
                SELECT concept, mastery
                FROM concept_mastery
                WHERE project_id = :project_id
                  AND user_id = :user_id
                ORDER BY mastery ASC
                LIMIT 20
            """),
            {"project_id": project_id, "user_id": user_id}
        ).mappings().all()

        # --------------------------------------------------
        # 2. Update persistent learning context
        # --------------------------------------------------
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

        attempts = int(quiz["attempts"] or 0)
        average = float(quiz["average"] or 0)
        best = float(quiz["best"] or 0)

        if attempts:
            db.execute(
                text("""
                    INSERT INTO learning_context
                    (project_id, user_id, category, key, value, source, confidence)
                    VALUES
                    (:project_id, :user_id, 'performance',
                     'latest_workflow_summary', :value, 'workflow', 1.0)
                    ON CONFLICT (project_id, user_id, category, key)
                    DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "project_id": project_id,
                    "user_id": user_id,
                    "value": (
                        f"{attempts} quiz attempt(s); average {average:.1f}%; "
                        f"best {best:.1f}%."
                    ),
                }
            )

        # --------------------------------------------------
        # 3. Detect weak concepts
        # --------------------------------------------------
        weak = [
            row for row in mastery
            if float(row["mastery"] or 0) < 50
        ]

        strong = [
            row for row in mastery
            if float(row["mastery"] or 0) >= 75
        ]

        for row in weak:
            concept = str(row["concept"])
            score = float(row["mastery"] or 0)

            db.execute(
                text("""
                    INSERT INTO learning_context
                    (project_id, user_id, category, key, value, source, confidence)
                    VALUES
                    (:project_id, :user_id, 'weakness', :key, :value,
                     'workflow', 0.95)
                    ON CONFLICT (project_id, user_id, category, key)
                    DO UPDATE SET
                        value = EXCLUDED.value,
                        confidence = EXCLUDED.confidence,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "project_id": project_id,
                    "user_id": user_id,
                    "key": "workflow_" + concept.lower().replace(" ", "_")[:70],
                    "value": (
                        f"{concept} currently has {score:.1f}% mastery. "
                        "Review and practice this concept."
                    ),
                }
            )

        # --------------------------------------------------
        # 4. Generate rule-based next actions
        # --------------------------------------------------
        recommendations = []

        if weak:
            concepts = ", ".join(
                str(row["concept"]) for row in weak[:3]
            )
            recommendations.append({
                "text": f"Review and practice these weak concepts: {concepts}.",
                "reason": "Concept mastery is below 50%.",
                "priority": "high",
            })
        elif attempts and average < 70:
            recommendations.append({
                "text": "Complete a short practice quiz focused on foundational concepts.",
                "reason": f"Average quiz performance is {average:.1f}%.",
                "priority": "high",
            })
        elif strong:
            recommendations.append({
                "text": "Try a more challenging assessment to extend your understanding.",
                "reason": "Several concepts currently show strong mastery.",
                "priority": "medium",
            })
        else:
            recommendations.append({
                "text": "Complete a quiz or open-ended assessment to collect more learning evidence.",
                "reason": "More learning evidence is needed.",
                "priority": "medium",
            })

        # Keep latest workflow recommendations manageable.
        db.execute(
            text("""
                DELETE FROM learning_recommendations
                WHERE project_id = :project_id
                  AND user_id = :user_id
            """),
            {"project_id": project_id, "user_id": user_id}
        )

        for item in recommendations:
            db.execute(
                text("""
                    INSERT INTO learning_recommendations
                    (project_id, user_id, recommendation, reason, priority)
                    VALUES
                    (:project_id, :user_id, :recommendation, :reason, :priority)
                """),
                {
                    "project_id": project_id,
                    "user_id": user_id,
                    "recommendation": item["text"],
                    "reason": item["reason"],
                    "priority": item["priority"],
                }
            )

        result = {
            "quiz_attempts": attempts,
            "average_quiz_score": round(average, 2),
            "weak_concepts": [str(row["concept"]) for row in weak],
            "strong_concepts": [str(row["concept"]) for row in strong],
            "recommendations_created": len(recommendations),
        }

        db.execute(
            text("""
                UPDATE learning_workflows
                SET status = 'completed',
                    result = CAST(:result AS JSONB),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {
                "id": workflow_id,
                "result": json.dumps(result),
            }
        )
        db.commit()

    except Exception as error:
        db.rollback()

        try:
            db.execute(
                text("""
                    UPDATE learning_workflows
                    SET status = 'failed',
                        error_message = :error,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """),
                {"id": workflow_id, "error": str(error)}
            )
            db.commit()
        except Exception:
            db.rollback()

    finally:
        db.close()


@router.post("/process")
def start_learning_workflow(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    verify_project(db, request.project_id, user.id)
    ensure_tables(db)

    result = db.execute(
        text("""
            INSERT INTO learning_workflows
            (project_id, user_id, workflow_type, trigger, status)
            VALUES
            (:project_id, :user_id, 'learning_update',
             :trigger, 'queued')
            RETURNING id
        """),
        {
            "project_id": request.project_id,
            "user_id": str(user.id),
            "trigger": request.trigger,
        }
    ).first()

    workflow_id = int(result[0])
    db.commit()

    background_tasks.add_task(
        process_learning_workflow,
        workflow_id,
        request.project_id,
        str(user.id),
    )

    return {
        "workflow_id": workflow_id,
        "status": "queued",
        "message": "Learning workflow started in the background.",
    }


@router.get("/{project_id}/status/{workflow_id}")
def workflow_status(
    project_id: str,
    workflow_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    verify_project(db, project_id, user.id)
    ensure_tables(db)

    row = db.execute(
        text("""
            SELECT id, workflow_type, trigger, status,
                   result, error_message, created_at, updated_at
            FROM learning_workflows
            WHERE id = :id
              AND project_id = :project_id
              AND user_id = :user_id
        """),
        {
            "id": workflow_id,
            "project_id": project_id,
            "user_id": str(user.id),
        }
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return dict(row)


@router.get("/{project_id}/recommendations")
def workflow_recommendations(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    verify_project(db, project_id, user.id)
    ensure_tables(db)

    rows = db.execute(
        text("""
            SELECT id, recommendation, reason, priority, created_at
            FROM learning_recommendations
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                created_at DESC
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id),
        }
    ).mappings().all()

    return {
        "project_id": project_id,
        "recommendations": [dict(row) for row in rows],
    }
