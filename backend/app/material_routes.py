import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import Material, Project
from .workspace_routes import get_current_user

router = APIRouter(prefix="/materials", tags=["Materials"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload/{project_id}")
async def upload_material(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    project = db.get(Project, project_id)

    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project not found: {project_id}"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    material_id = str(uuid.uuid4())

    safe_filename = f"{material_id}.pdf"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    content = await file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    material = Material(
        id=material_id,
        project_id=project.id,
        filename=file.filename,
        file_path=file_path,
        status="queued"
    )

    db.add(material)
    db.commit()
    db.refresh(material)

    return {
        "message": "PDF uploaded successfully",
        "material_id": material.id,
        "filename": material.filename,
        "status": material.status
    }
@router.get("/{material_id}/status")
def get_material_status(
    material_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    material = db.get(Material, material_id)

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )

    return {
        "material_id": material.id,
        "filename": material.filename,
        "status": material.status
    }