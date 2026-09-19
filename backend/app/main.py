from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .workspace_routes import router as workspace_router
from .material_routes import router as material_router
from .database import engine, Base
from . import models
from .auth_routes import router as auth_router
from .tutor_routes import router as tutor_router
from .quiz_routes import router as quiz_router
from .progress_routes import router as progress_router
from .assessment_routes import router as assessment_router
from .growth_routes import router as growth_router
from .activity_routes import router as activity_router
from .analytics_routes import router as analytics_router
from .observability_routes import router as observability_router
from .admin_routes import router as admin_router
from .context_routes import router as context_router
from .evaluation_routes import router as evaluation_router
from .workflow_routes import router as workflow_router
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Study Companion API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": "AI Study Companion API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}

app.include_router(workspace_router)
app.include_router(material_router)
app.include_router(tutor_router)
app.include_router(quiz_router)
app.include_router(progress_router)
app.include_router(assessment_router)
app.include_router(growth_router)
app.include_router(activity_router)
app.include_router(analytics_router)
app.include_router(observability_router)
app.include_router(admin_router)
app.include_router(context_router)
app.include_router(evaluation_router)
app.include_router(workflow_router)