from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user


router = APIRouter(
    prefix="/growth",
    tags=["Growth & Recommendations"]
)


def verify_project(project_id: str, db: Session, user):
    result = db.execute(
        text("""
            SELECT p.id
            FROM projects p
            JOIN spaces s ON s.id = p.space_id
            WHERE p.id = :project_id
              AND s.user_id = :user_id
        """),
        {
            "project_id": project_id,
            "user_id": str(user.id)
        }
    ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )


def ensure_tables(db: Session):
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

    db.execute(text("""
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
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS concept_mastery (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            concept VARCHAR NOT NULL,
            mastery FLOAT NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id, concept)
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS activity_events (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    db.commit()


def get_learning_data(project_id: str, user_id: str, db: Session):
    ensure_tables(db)

    mastery_rows = db.execute(
        text("""
            SELECT concept, mastery, updated_at
            FROM concept_mastery
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY mastery ASC
        """),
        {
            "project_id": project_id,
            "user_id": user_id
        }
    ).mappings().all()

    quiz_rows = db.execute(
        text("""
            SELECT score, total, percentage, created_at
            FROM quiz_results
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 20
        """),
        {
            "project_id": project_id,
            "user_id": user_id
        }
    ).mappings().all()

    assessment_rows = db.execute(
        text("""
            SELECT concept, score, created_at
            FROM assessment_results
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 50
        """),
        {
            "project_id": project_id,
            "user_id": user_id
        }
    ).mappings().all()

    activity_rows = db.execute(
        text("""
            SELECT event_type, created_at
            FROM activity_events
            WHERE project_id = :project_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 30
        """),
        {
            "project_id": project_id,
            "user_id": user_id
        }
    ).mappings().all()

    return mastery_rows, quiz_rows, assessment_rows, activity_rows


def build_growth(
    mastery_rows,
    quiz_rows,
    assessment_rows,
    activity_rows
):
    # --------------------------------------------------------
    # Concept-level growth
    # --------------------------------------------------------

    improving = []
    stable = []
    attention = []
    strengths = []

    for row in mastery_rows:
        concept = str(row["concept"])
        mastery = float(row["mastery"])

        if mastery >= 75:
            strengths.append(
                f"{concept} is currently a strong area at {mastery:.0f}% mastery."
            )
        elif mastery < 50:
            attention.append(
                f"{concept} requires attention ({mastery:.0f}% estimated mastery)."
            )
        else:
            stable.append(
                f"{concept} is developing steadily ({mastery:.0f}% estimated mastery)."
            )

    # --------------------------------------------------------
    # Assessment evidence
    # --------------------------------------------------------

    assessment_by_concept = {}

    for row in assessment_rows:
        concept = str(row["concept"])
        score = float(row["score"])

        assessment_by_concept.setdefault(
            concept,
            []
        ).append(score)

    for concept, scores in assessment_by_concept.items():
        if len(scores) >= 2:
            recent = scores[0]
            previous = sum(scores[1:]) / len(scores[1:])

            if recent >= previous + 10:
                improving.append(
                    f"{concept} is improving based on recent assessment performance "
                    f"({recent:.0f}% vs {previous:.0f}% earlier evidence)."
                )
            elif recent <= previous - 10:
                attention.append(
                    f"{concept} has declined in recent assessment performance "
                    f"({recent:.0f}% vs {previous:.0f}% earlier evidence)."
                )

    # --------------------------------------------------------
    # Quiz trend
    # --------------------------------------------------------

    quiz_average = 0.0
    latest_quiz = 0.0

    if quiz_rows:
        percentages = [
            float(row["percentage"])
            for row in quiz_rows
        ]

        quiz_average = sum(percentages) / len(percentages)
        latest_quiz = percentages[0]

        if len(percentages) >= 2:
            previous_average = sum(percentages[1:]) / len(percentages[1:])

            if latest_quiz >= previous_average + 5:
                improving.append(
                    f"Recent quiz performance is improving "
                    f"({latest_quiz:.0f}% latest vs {previous_average:.0f}% earlier average)."
                )
            elif latest_quiz <= previous_average - 5:
                attention.append(
                    f"Recent quiz performance needs attention "
                    f"({latest_quiz:.0f}% latest vs {previous_average:.0f}% earlier average)."
                )
            else:
                stable.append(
                    f"Quiz performance is relatively stable around {quiz_average:.0f}%."
                )

    # --------------------------------------------------------
    # Fallback evidence when mastery has not been populated yet
    # --------------------------------------------------------

    if not mastery_rows and quiz_rows:
        if quiz_average >= 75:
            strengths.append(
                f"Overall quiz performance is strong at {quiz_average:.0f}%."
            )
        elif quiz_average < 50:
            attention.append(
                f"Overall quiz performance requires attention at {quiz_average:.0f}%."
            )
        else:
            stable.append(
                f"Overall quiz performance is developing at {quiz_average:.0f}%."
            )

    if not assessment_rows and not quiz_rows and not mastery_rows:
        return None

    # Remove duplicates while preserving order.
    def unique(items):
        return list(dict.fromkeys(items))

    improving = unique(improving)
    stable = unique(stable)
    attention = unique(attention)
    strengths = unique(strengths)

    # --------------------------------------------------------
    # Recommended next action
    # --------------------------------------------------------

    if attention:
        next_action = (
            "Review the concepts requiring attention, then complete a short "
            "practice quiz or open-ended assessment to check improvement."
        )
    elif improving:
        next_action = (
            "Continue practicing the improving concepts and complete another "
            "short assessment to confirm that the progress is sustained."
        )
    else:
        next_action = (
            "Continue learning from the uploaded material and complete another "
            "quiz or assessment to collect more learning evidence."
        )

    return {
        "summary": (
            f"Learning evidence includes {len(quiz_rows)} quiz attempt(s), "
            f"{len(assessment_rows)} assessment result(s), and "
            f"{len(mastery_rows)} tracked concept(s)."
        ),
        "improving": improving,
        "stable": stable,
        "strengths": strengths,
        "areas_needing_attention": attention,
        "growth_insights": (
            improving
            + stable
            + attention
        ),
        "next_action": next_action,
        "quiz_average": round(quiz_average, 1),
        "latest_quiz": round(latest_quiz, 1),
        "assessment_count": len(assessment_rows),
        "mastery_count": len(mastery_rows)
    }


@router.get("/{project_id}")
def get_growth(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(project_id, db, user)

    try:
        mastery, quizzes, assessments, activity = get_learning_data(
            project_id,
            str(user.id),
            db
        )

        analysis = build_growth(
            mastery,
            quizzes,
            assessments,
            activity
        )

        return {
            "project_id": project_id,
            "analysis": analysis
        }

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        print("Growth analysis error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to generate growth analysis"
        )


@router.get("/{project_id}/recommendations")
def get_recommendations(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    verify_project(project_id, db, user)

    try:
        mastery, quizzes, assessments, activity = get_learning_data(
            project_id,
            str(user.id),
            db
        )

        analysis = build_growth(
            mastery,
            quizzes,
            assessments,
            activity
        )

        if not analysis:
            return {
                "project_id": project_id,
                "recommendations": []
            }

        recommendations = []

        if analysis["areas_needing_attention"]:
            for area in analysis["areas_needing_attention"][:3]:
                recommendations.append({
                    "title": "Review a weak area",
                    "reason": area,
                    "priority": "high",
                    "action": (
                        "Review the related material and complete a short "
                        "practice quiz or open-ended assessment."
                    )
                })

        if analysis["improving"]:
            recommendations.append({
                "title": "Reinforce improving concepts",
                "reason": analysis["improving"][0],
                "priority": "medium",
                "action": (
                    "Practice the concept again and verify your understanding "
                    "with another assessment."
                )
            })

        if not recommendations:
            recommendations.append({
                "title": "Continue learning",
                "reason": (
                    "More learning evidence is needed to identify a specific "
                    "weak concept."
                ),
                "priority": "medium",
                "action": (
                    "Complete another quiz or assessment using the uploaded "
                    "study material."
                )
            })

        return {
            "project_id": project_id,
            "recommendations": recommendations[:5]
        }

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        print("Recommendation error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to generate recommendations"
        )
