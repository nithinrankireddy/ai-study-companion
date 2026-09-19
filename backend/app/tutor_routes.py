import os
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .workspace_routes import get_current_user
from .models import User
from .ai_observability import log_ai_call


router = APIRouter(
    prefix="/tutor",
    tags=["AI Tutor"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class TutorRequest(BaseModel):
    project_id: str
    question: str


# ============================================================
# SEARCH MATERIAL
# ============================================================

def search_material(
    db: Session,
    project_id: str,
    question: str
):
    words = [
        word.strip(".,?!:;()[]{}\"'")
        for word in question.lower().split()
        if len(word.strip(".,?!:;()[]{}\"'")) > 2
    ]

    if not words:
        return []

    conditions = []
    parameters = {
        "project_id": project_id
    }

    for index, word in enumerate(words[:8]):
        key = f"word_{index}"

        conditions.append(
            f"LOWER(mc.content) LIKE :{key}"
        )

        parameters[key] = f"%{word}%"

    where_clause = " OR ".join(conditions)

    query = text(
        f"""
        SELECT
            mc.id,
            mc.material_id,
            mc.chunk_index,
            mc.content
        FROM material_chunks mc
        JOIN materials m
            ON m.id = mc.material_id
        WHERE m.project_id = :project_id
          AND ({where_clause})
        ORDER BY mc.chunk_index
        LIMIT 6
        """
    )

    result = db.execute(
        query,
        parameters
    )

    return result.fetchall()


# ============================================================
# MOCK / DEVELOPMENT TUTOR
# ============================================================

def mock_tutor_answer(
    question: str,
    chunks
):
    """
    Development fallback used when AI_MOCK_MODE=true.

    This does NOT pretend to be a Gemini response.
    It simply proves the retrieval -> context -> citation
    flow without consuming Gemini API quota.
    """

    first_chunk = chunks[0]

    preview = first_chunk.content.strip()

    if len(preview) > 900:
        preview = preview[:900] + "..."

    return (
        "### Development Tutor Response\n\n"
        "Gemini API is currently disabled in development mode, "
        "so no external AI request was made.\n\n"
        f"Your question was:\n**{question}**\n\n"
        "The retrieved study material contains the following "
        "relevant content:\n\n"
        f"> {preview.replace(chr(10), ' ')}\n\n"
        "This confirms that the Tutor retrieved material from "
        "your uploaded document and can attach source citations. "
        "Set `AI_MOCK_MODE=false` to use Gemini again."
    )


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    question: str,
    context: str,
    db: Session,
    project_id: str,
    user_id
):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured"
        )

    model_name = "gemini-3.5-flash"
    ai_started_at = time.perf_counter()

    try:
        from google import genai

        client = genai.Client(
            api_key=api_key
        )

        prompt = f"""
You are an AI Study Tutor.

Answer the student's question using the study
material provided below.

IMPORTANT RULES:

1. Use the provided study material as the primary source.
2. Explain the answer clearly for a student.
3. If the material contains the answer, stay consistent
   with the material's terminology and explanation.
4. If the answer is not present in the material,
   clearly say that the uploaded material does not
   contain enough information to answer it.
5. Do not invent facts.
6. Use examples when they help understanding.
7. Use headings and bullet points when appropriate.

STUDY MATERIAL:

{context}

STUDENT QUESTION:

{question}

Now answer the student's question.
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        log_ai_call(
            db=db,
            project_id=project_id,
            user_id=user_id,
            feature="ai_tutor",
            model=model_name,
            started_at=ai_started_at,
            response=response,
            status="success"
        )

        return response.text

    except HTTPException:
        raise

    except Exception as error:
        error_message = str(error)

        print(
            f"Gemini error: {error_message}"
        )

        try:
            log_ai_call(
                db=db,
                project_id=project_id,
                user_id=user_id,
                feature="ai_tutor",
                model=model_name,
                started_at=ai_started_at,
                status="failure",
                error_message=error_message
            )
        except Exception as logging_error:
            print(
                f"AI observability logging failed: {logging_error}"
            )

        # ----------------------------------------------------
        # Gemini quota exhausted
        # ----------------------------------------------------

        if (
            "429" in error_message
            or "RESOURCE_EXHAUSTED" in error_message
            or "quota" in error_message.lower()
        ):
            raise HTTPException(
                status_code=429,
                detail=(
                    "AI Tutor quota is temporarily exhausted. "
                    "Set AI_MOCK_MODE=true in backend/.env to "
                    "continue testing the Tutor without using "
                    "Gemini API quota."
                )
            )

        raise HTTPException(
            status_code=500,
            detail="AI Tutor service failed. Please try again later."
        )


# ============================================================
# ASK AI TUTOR
# ============================================================

@router.post("/ask")
def ask_tutor(
    data: TutorRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not data.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    # --------------------------------------------------------
    # Verify project belongs to current user
    # --------------------------------------------------------

    project_check = db.execute(
        text(
            """
            SELECT p.id
            FROM projects p
            JOIN spaces s
                ON s.id = p.space_id
            WHERE p.id = :project_id
              AND s.user_id = :user_id
            """
        ),
        {
            "project_id": data.project_id,
            "user_id": user.id
        }
    ).first()

    if not project_check:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    # --------------------------------------------------------
    # Search PDF chunks
    # --------------------------------------------------------

    chunks = search_material(
        db,
        data.project_id,
        data.question
    )

    # --------------------------------------------------------
    # No relevant material found
    # --------------------------------------------------------

    if not chunks:
        return {
            "answer": (
                "I couldn't find relevant information in "
                "your uploaded study material for this question."
            ),
            "sources": [],
            "project_id": data.project_id
        }

    # --------------------------------------------------------
    # Build context + citations
    # --------------------------------------------------------

    context_parts = []
    sources = []

    for chunk in chunks:
        context_parts.append(
            f"""
[Chunk {chunk.chunk_index}]

{chunk.content}
"""
        )

        sources.append({
            "material_id": str(chunk.material_id),
            "chunk_index": chunk.chunk_index
        })

    context = "\n".join(context_parts)

    # --------------------------------------------------------
    # Development mode
    # --------------------------------------------------------

    mock_mode = os.getenv(
        "AI_MOCK_MODE",
        "false"
    ).strip().lower() == "true"

    if mock_mode:
        answer = mock_tutor_answer(
            data.question,
            chunks
        )

        return {
            "answer": answer,
            "sources": sources,
            "project_id": data.project_id,
            "mock_mode": True
        }

    # --------------------------------------------------------
    # Ask Gemini
    # --------------------------------------------------------

    answer = ask_gemini(
        data.question,
        context,
        db,
        data.project_id,
        user.id
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "answer": answer,
        "sources": sources,
        "project_id": data.project_id,
        "mock_mode": False
    }
