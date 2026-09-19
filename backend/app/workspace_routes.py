from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt

from .database import get_db
from .models import User, Space, Project
from .auth import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/workspace", tags=["Workspace"])
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class SpaceCreate(BaseModel):
    name: str
    description: str = ""


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    learning_goal: str = ""


@router.post("/spaces")
def create_space(
    data: SpaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    space = Space(
        user_id=user.id,
        name=data.name,
        description=data.description
    )

    db.add(space)
    db.commit()
    db.refresh(space)

    return space


@router.get("/spaces")
def get_spaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return db.query(Space).filter(
        Space.user_id == user.id
    ).all()


@router.post("/spaces/{space_id}/projects")
def create_project(
    space_id: str,
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    space = db.query(Space).filter(
        Space.id == space_id,
        Space.user_id == user.id
    ).first()

    if not space:
        raise HTTPException(
            status_code=404,
            detail="Space not found"
        )

    project = Project(
        space_id=space.id,
        name=data.name,
        description=data.description,
        learning_goal=data.learning_goal
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get("/spaces/{space_id}/projects")
def get_projects(
    space_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    space = db.query(Space).filter(
        Space.id == space_id,
        Space.user_id == user.id
    ).first()

    if not space:
        raise HTTPException(
            status_code=404,
            detail="Space not found"
        )

    return db.query(Project).filter(
        Project.space_id == space.id
    ).all()

@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
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