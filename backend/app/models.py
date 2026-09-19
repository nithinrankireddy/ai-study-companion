from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    spaces = relationship("Space", back_populates="user")


class Space(Base):
    __tablename__ = "spaces"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="spaces")
    projects = relationship("Project", back_populates="space")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    space_id = Column(String, ForeignKey("spaces.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    learning_goal = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    space = relationship("Space", back_populates="projects")
    materials = relationship("Material", back_populates="project")
    concepts = relationship("Concept", back_populates="project")


class Material(Base):
    __tablename__ = "materials"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String)
    status = Column(String, default="queued")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="materials")


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    mastery = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="concepts")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"))
    event_type = Column(String, nullable=False)
    event_metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)