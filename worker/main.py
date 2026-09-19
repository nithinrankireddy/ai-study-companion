import os
import sys
import time
from pathlib import Path

# Add backend directory to Python import path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from pypdf import PdfReader
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Material


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://study_user:study_password@localhost:5432/study_companion"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# ============================================================
# PATHS
# ============================================================

# Project root:
# /home/rgukt/ai-study-companion

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "backend" / "uploads"

# If worker is inside:
# /home/rgukt/ai-study-companion/worker
#
# BASE_DIR becomes:
# /home/rgukt/ai-study-companion


# ============================================================
# CHUNK SETTINGS
# ============================================================

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


# ============================================================
# CREATE CHUNKS TABLE
# ============================================================

def create_chunks_table():

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS material_chunks (
                    id SERIAL PRIMARY KEY,
                    material_id VARCHAR NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    print("Material chunks table ready.")


# ============================================================
# TEXT EXTRACTION
# ============================================================

def extract_pdf_text(file_path):

    print(f"Reading PDF: {file_path}")

    reader = PdfReader(str(file_path))

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        try:
            page_text = page.extract_text() or ""

            if page_text.strip():

                pages.append(
                    f"\n--- Page {page_number} ---\n"
                    f"{page_text}"
                )

        except Exception as error:

            print(
                f"Warning: Could not read page "
                f"{page_number}: {error}"
            )

    full_text = "\n".join(pages)

    return full_text


# ============================================================
# TEXT CHUNKING
# ============================================================

def split_text(text_content):

    text_content = text_content.strip()

    if not text_content:
        return []

    chunks = []

    start = 0

    text_length = len(text_content)

    while start < text_length:

        end = start + CHUNK_SIZE

        chunk = text_content[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - CHUNK_OVERLAP

    return chunks


# ============================================================
# SAVE CHUNKS
# ============================================================

def save_chunks(material_id, chunks):

    with engine.begin() as connection:

        # Remove old chunks if this material is processed again
        connection.execute(
            text(
                """
                DELETE FROM material_chunks
                WHERE material_id = :material_id
                """
            ),
            {
                "material_id": material_id
            }
        )

        for index, chunk in enumerate(chunks):

            connection.execute(
                text(
                    """
                    INSERT INTO material_chunks
                    (
                        material_id,
                        chunk_index,
                        content
                    )
                    VALUES
                    (
                        :material_id,
                        :chunk_index,
                        :content
                    )
                    """
                ),
                {
                    "material_id": material_id,
                    "chunk_index": index,
                    "content": chunk
                }
            )


# ============================================================
# UPDATE MATERIAL STATUS
# ============================================================

def update_material_status(material_id, status):

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                UPDATE materials
                SET status = :status
                WHERE id = :material_id
                """
            ),
            {
                "status": status,
                "material_id": material_id
            }
        )


# ============================================================
# FIND PDF PATH
# ============================================================

def resolve_file_path(file_path):

    path = Path(file_path)

    # Already absolute
    if path.is_absolute() and path.exists():
        return path

    # Try project root
    candidate = BASE_DIR / path

    if candidate.exists():
        return candidate

    # Try backend directory
    candidate = BASE_DIR / "backend" / path

    if candidate.exists():
        return candidate

    # Try uploads directory using filename
    candidate = UPLOAD_DIR / path.name

    if candidate.exists():
        return candidate

    return None


# ============================================================
# PROCESS ONE MATERIAL
# ============================================================

def process_material(material):

    material_id = str(material.id)

    print()
    print("=" * 60)
    print(f"Processing: {material.filename}")
    print(f"Material ID: {material_id}")
    print(f"Database path: {material.file_path}")
    print("=" * 60)

    file_path = resolve_file_path(material.file_path)

    if file_path is None:

        print(
            f"ERROR: PDF file not found: "
            f"{material.file_path}"
        )

        update_material_status(
            material_id,
            "failed"
        )

        return

    print(f"Found PDF: {file_path}")

    try:

        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        full_text = extract_pdf_text(file_path)

        if not full_text.strip():

            print("ERROR: No readable text found in PDF.")

            update_material_status(
                material_id,
                "failed"
            )

            return

        print(
            f"Extracted {len(full_text)} characters."
        )

        # ----------------------------------------------------
        # Split into chunks
        # ----------------------------------------------------

        chunks = split_text(full_text)

        print(
            f"Created {len(chunks)} text chunks."
        )

        # ----------------------------------------------------
        # Save chunks
        # ----------------------------------------------------

        save_chunks(
            material_id,
            chunks
        )

        # ----------------------------------------------------
        # Mark processed
        # ----------------------------------------------------

        update_material_status(
            material_id,
            "processed"
        )

        print()
        print(f"SUCCESS: {material.filename}")
        print(
            f"Stored {len(chunks)} chunks."
        )
        print("Status: processed")
        print()

    except Exception as error:

        print()
        print(
            f"ERROR while processing "
            f"{material.filename}: {error}"
        )

        update_material_status(
            material_id,
            "failed"
        )


# ============================================================
# PROCESS QUEUE
# ============================================================

def process_queue():

    print()
    print("==========================================")
    print("AI Study Companion Worker")
    print("==========================================")
    print("Waiting for queued materials...")
    print()

    create_chunks_table()

    while True:

        db = SessionLocal()

        try:

            material = (
                db.query(Material)
                .filter(
                    Material.status == "queued"
                )
                .order_by(
                    Material.created_at.asc()
                )
                .first()
            )

            if material:

                process_material(material)

            else:

                time.sleep(3)

        except Exception as error:

            print(
                f"Worker error: {error}"
            )

            time.sleep(3)

        finally:

            db.close()


# ============================================================
# START WORKER
# ============================================================

if __name__ == "__main__":

    process_queue()