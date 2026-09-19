from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user
from .models import User

router = APIRouter(prefix="/context", tags=["Learning Context"])


def ensure_context_table(db: Session):
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


def verify_project_access(db: Session, project_id: str, user_id):
    row = db.execute(text("""
        SELECT p.id
        FROM projects p
        JOIN spaces s ON s.id = p.space_id
        WHERE p.id = :project_id AND s.user_id = :user_id
    """), {"project_id": project_id, "user_id": str(user_id)}).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")


def sync_learning_context(db: Session, project_id: str, user_id):
    """Build persistent learner context from existing data. No Gemini call."""
    ensure_context_table(db)
    uid = str(user_id)

    def upsert(category, key, value, source="system", confidence=1.0):
        db.execute(text("""
            INSERT INTO learning_context
                (project_id, user_id, category, key, value, source, confidence)
            VALUES
                (:project_id, :user_id, :category, :key, :value, :source, :confidence)
            ON CONFLICT (project_id, user_id, category, key)
            DO UPDATE SET
                value = EXCLUDED.value,
                source = EXCLUDED.source,
                confidence = EXCLUDED.confidence,
                updated_at = CURRENT_TIMESTAMP
        """), {
            "project_id": project_id, "user_id": uid, "category": category,
            "key": key, "value": value, "source": source,
            "confidence": confidence,
        })

    try:
        row = db.execute(text("""
            SELECT COUNT(*) AS attempts,
                   COALESCE(AVG(percentage), 0) AS average_percentage,
                   COALESCE(MAX(percentage), 0) AS best_percentage
            FROM quiz_results
            WHERE project_id = :project_id AND user_id = :user_id
        """), {"project_id": project_id, "user_id": uid}).mappings().first()
        attempts = int(row["attempts"] or 0)
        if attempts:
            avg = float(row["average_percentage"] or 0)
            best = float(row["best_percentage"] or 0)
            upsert("performance", "quiz_summary",
                   f"{attempts} quiz attempt(s); average score {avg:.1f}%; best score {best:.1f}%.",
                   "quiz_results")
            if avg < 50:
                upsert("learning_need", "quiz_performance",
                       "Quiz performance indicates foundational concepts may need reinforcement.",
                       "quiz_results", 0.9)
            elif avg >= 75:
                upsert("strength", "quiz_performance",
                       "Quiz performance indicates strong recent understanding.",
                       "quiz_results", 0.9)
            else:
                upsert("development", "quiz_performance",
                       "Quiz performance indicates developing understanding.",
                       "quiz_results", 0.8)
    except Exception as error:
        print("Quiz context sync skipped:", error)
        db.rollback()
        ensure_context_table(db)

    try:
        row = db.execute(text("""
            SELECT COUNT(*) AS attempts, COALESCE(AVG(score), 0) AS average_score
            FROM assessment_results
            WHERE project_id = :project_id AND user_id = :user_id
        """), {"project_id": project_id, "user_id": uid}).mappings().first()
        attempts = int(row["attempts"] or 0)
        if attempts:
            avg = float(row["average_score"] or 0)
            upsert("performance", "assessment_summary",
                   f"{attempts} assessment result(s); average score {avg:.1f}.",
                   "assessment_results")
    except Exception as error:
        print("Assessment context sync skipped:", error)
        db.rollback()
        ensure_context_table(db)

    try:
        rows = db.execute(text("""
            SELECT concept, mastery
            FROM concept_mastery
            WHERE project_id = :project_id AND user_id = :user_id
            ORDER BY mastery ASC LIMIT 20
        """), {"project_id": project_id, "user_id": uid}).mappings().all()
        for row in rows:
            concept = str(row["concept"])
            mastery = float(row["mastery"] or 0)
            safe_key = "concept_" + "_".join(concept.lower().split())[:80]
            if mastery < 50:
                category = "weakness"
                value = f"{concept}: mastery is {mastery:.1f}%, so this concept may need reinforcement."
            elif mastery >= 75:
                category = "strength"
                value = f"{concept}: mastery is {mastery:.1f}%, indicating strong understanding."
            else:
                category = "development"
                value = f"{concept}: mastery is {mastery:.1f}%, indicating developing understanding."
            upsert(category, safe_key, value, "concept_mastery", 0.9)
    except Exception as error:
        print("Concept mastery context sync skipped:", error)
        db.rollback()
        ensure_context_table(db)

    db.commit()


class LearningContextRequest(BaseModel):
    category: str
    key: str
    value: str
    source: str = "manual"
    confidence: float = 1.0


@router.post("/{project_id}")
def create_or_update_context(project_id: str, data: LearningContextRequest,
                             db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    verify_project_access(db, project_id, user.id)
    ensure_context_table(db)
    confidence = max(0.0, min(1.0, float(data.confidence)))
    db.execute(text("""
        INSERT INTO learning_context
            (project_id, user_id, category, key, value, source, confidence)
        VALUES
            (:project_id, :user_id, :category, :key, :value, :source, :confidence)
        ON CONFLICT (project_id, user_id, category, key)
        DO UPDATE SET value = EXCLUDED.value, source = EXCLUDED.source,
                      confidence = EXCLUDED.confidence, updated_at = CURRENT_TIMESTAMP
    """), {
        "project_id": project_id, "user_id": str(user.id), "category": data.category,
        "key": data.key, "value": data.value, "source": data.source,
        "confidence": confidence,
    })
    db.commit()
    return {"message": "Learning context saved", "project_id": project_id,
            "category": data.category, "key": data.key}


@router.get("/{project_id}")
def get_context(project_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    verify_project_access(db, project_id, user.id)
    sync_learning_context(db, project_id, user.id)
    rows = db.execute(text("""
        SELECT id, category, key, value, source, confidence, created_at, updated_at
        FROM learning_context
        WHERE project_id = :project_id AND user_id = :user_id
        ORDER BY confidence DESC, updated_at DESC
    """), {"project_id": project_id, "user_id": str(user.id)}).mappings().all()
    return {"project_id": project_id, "count": len(rows), "context": [dict(r) for r in rows]}


@router.get("/{project_id}/relevant")
def get_relevant_context(project_id: str, query: str = "",
                         db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    verify_project_access(db, project_id, user.id)
    sync_learning_context(db, project_id, user.id)
    words = [w.strip(".,?!:;()[]{}\"'") for w in query.lower().split()
             if len(w.strip(".,?!:;()[]{}\"'")) > 2]
    params = {"project_id": project_id, "user_id": str(user.id)}
    if words:
        conditions = []
        for i, word in enumerate(words[:8]):
            k = f"word_{i}"
            conditions.append(f"(LOWER(category) LIKE :{k} OR LOWER(key) LIKE :{k} OR LOWER(value) LIKE :{k})")
            params[k] = f"%{word}%"
        sql = f"""
            SELECT id, category, key, value, source, confidence
            FROM learning_context
            WHERE project_id = :project_id AND user_id = :user_id
              AND ({' OR '.join(conditions)})
            ORDER BY confidence DESC, updated_at DESC LIMIT 10
        """
    else:
        sql = """
            SELECT id, category, key, value, source, confidence
            FROM learning_context
            WHERE project_id = :project_id AND user_id = :user_id
            ORDER BY confidence DESC, updated_at DESC LIMIT 10
        """
    rows = db.execute(text(sql), params).mappings().all()
    return {"project_id": project_id, "query": query,
            "count": len(rows), "context": [dict(r) for r in rows]}
