AI Study Companion

AI-powered learning and growth workspace that connects learning materials, grounded AI tutoring, adaptive quizzes, open-ended assessment, concept mastery, growth analysis, recommendations, analytics, persistent learning context, and background workflows.

Overview

AI Study Companion is designed around a continuous learning loop:

Space → Project → Material → Knowledge → Tutor → Quiz → Assessment → Mastery → Growth → Recommendation → Analytics → Continue Learning

The application is built as a full-stack prototype with:

Next.js / React frontend

FastAPI / Python backend

PostgreSQL database

Background PDF processing worker

Google Gemini for selected AI learning experiences

Project-scoped retrieval and persistent learner context

AI observability and rule-based evaluation

User and admin experiences

Core Features

Learning Workspace

User authentication

Spaces and Projects

Project-specific learning goals

PDF learning-material upload

Background document processing

Searchable material chunks

Project-scoped knowledge retrieval

AI Learning

AI Tutor grounded in uploaded Project material

Supporting source information for Tutor responses

Unsupported-question handling

Adaptive multiple-choice quiz generation

Open-ended assessment generation and evaluation

Persistent relevant learning context

Concept mastery tracking

Growth analysis

Personalized learning recommendations

Analytics & Operations

Project activity tracking

Quiz performance analytics

Assessment performance analytics

Concept mastery information

AI activity analytics

Background learning workflow

AI observability

AI evaluation

Admin dashboard

System health visibility

Architecture

┌──────────────────────────────────────────────┐
│              Next.js Frontend                │
│      User Workspace + Admin Dashboard        │
└──────────────────────┬───────────────────────┘
                       │ JWT / REST API
                       ▼
┌──────────────────────────────────────────────┐
│               FastAPI Backend                │
│                                              │
│ Auth / Workspace / Materials / Tutor        │
│ Quiz / Assessment / Progress / Analytics    │
│ Growth / Context / Workflow / Evaluation    │
│ Observability / Admin                       │
└───────────────┬───────────────┬──────────────┘
                │               │
                ▼               ▼
        ┌─────────────┐   ┌───────────────┐
        │ PostgreSQL  │   │ Gemini API    │
        │ Learning    │   │ Tutor / Quiz  │
        │ State       │   │ Assessment    │
        └─────────────┘   └───────────────┘
                ▲
                │
        ┌───────┴────────┐
        │ Background     │
        │ Worker         │
        │ PDF Processing │
        └────────────────┘

Project data isolation

Learning material, retrieval, learning context, assessments, mastery, activity, and recommendations are scoped to the current user and Project where applicable. Protected backend operations verify ownership before returning Project-level data.

Repository Structure

ai-study-companion/
├── backend/
│   ├── app/
│   │   ├── auth.py
│   │   ├── auth_routes.py
│   │   ├── workspace_routes.py
│   │   ├── material_routes.py
│   │   ├── tutor_routes.py
│   │   ├── quiz_routes.py
│   │   ├── assessment_routes.py
│   │   ├── progress_routes.py
│   │   ├── growth_routes.py
│   │   ├── activity_routes.py
│   │   ├── analytics_routes.py
│   │   ├── context_routes.py
│   │   ├── workflow_routes.py
│   │   ├── evaluation_routes.py
│   │   ├── observability_routes.py
│   │   ├── admin_routes.py
│   │   └── main.py
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── admin/
│   │   ├── project/[id]/
│   │   ├── space/[id]/
│   │   └── page.tsx
│   ├── public/
│   └── package.json
│
├── worker/
│   └── main.py
│
├── docs/
├── .env.example
├── .gitignore
└── README.md

AI Architecture

Tutor

The Tutor follows this general flow:

User Question
      ↓
Current Project
      ↓
Relevant Material Retrieval
      ↓
Relevant Learning Context
      ↓
Gemini
      ↓
Grounded Answer + Sources

Material evidence is treated as the primary source for Project-specific answers. When evidence is insufficient, the Tutor is instructed not to confidently fabricate an answer.

Adaptive Quiz

Quiz generation considers available learning evidence such as:

Recent quiz performance

Average/latest performance

Quiz history

Recent activity

Project material

Current learning state

The implementation validates the generated structure before returning questions to the frontend.

Assessment

Open-ended assessment evaluation considers learning evidence such as:

Understanding

Accuracy

Relevance

Key concepts covered

Missing concepts

Reasoning where appropriate

Assessment results are persisted and can contribute to concept mastery and learning analysis.

Persistent Learning Context

The application stores relevant learner context such as:

Performance summaries

Strengths

Weaknesses

Concept mastery

Assessment evidence

Learning history

Only relevant context is selected for an AI task rather than sending the complete historical state on every request.

Background Processing

Material workflow

Upload PDF
   ↓
Queued
   ↓
Processing
   ↓
Text Extraction
   ↓
Chunk Creation
   ↓
Ready

The worker processes uploaded material outside the main interactive request path.

Learning workflow

Quiz Completed
      ↓
Workflow Queued
      ↓
Workflow Running
      ↓
Learning Evidence Analysis
      ↓
Learning Context Update
      ↓
Weak / Strong Concept Detection
      ↓
Recommendation
      ↓
Completed

The current prototype provides workflow states and basic failure handling. Durable distributed queues, stronger retry policies, and comprehensive idempotency are planned improvements.

AI Observability

AI calls can be recorded with:

Feature

Model

Success / failure

Latency

Prompt token count

Output token count

Total token count

Estimated cost

Error information

This supports investigation of AI performance and usage.

AI Evaluation

The project includes evaluation endpoints for:

Tutor groundedness and citation support

Retrieval relevance

Assessment quality

Recommendation quality

The current evaluator uses lightweight rule-based checks so quality evaluation can be performed without unnecessarily generating another AI response.

Security

JWT-based authentication

Protected API routes

Project ownership checks

Admin role checks

Project-scoped material retrieval

Structured validation of AI-generated data

Environment-based secret configuration

.env files excluded from Git

No API keys committed to the repository

Local Setup

Prerequisites

Python 3.10+

Node.js 20+

PostgreSQL

Git

A Gemini API key for AI-powered features

1. Clone

git clone https://github.com/nithinrankireddy/ai-study-companion.git
cd ai-study-companion

2. Backend

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

Configure the backend environment using the provided example:

cp .env.example .env

Set the required database and Gemini configuration in .env.

Start the API:

uvicorn app.main:app --reload

Backend API:

http://127.0.0.1:8000

Swagger:

http://127.0.0.1:8000/docs

3. Worker

From the backend directory:

source venv/bin/activate
python3 ../worker/main.py

The worker processes uploaded learning material.

4. Frontend

Open another terminal:

cd frontend
npm install
npm run dev

Frontend:

http://localhost:3000

Environment Variables

Never commit real secrets.

Example backend configuration:

DATABASE_URL=postgresql://study_user:study_password@localhost:5432/study_companion
GEMINI_API_KEY=your_gemini_api_key

Use the repository's .env.example as the configuration template.

Testing & Verification

Backend compilation

cd backend
source venv/bin/activate
python3 -m compileall app

Frontend production build

cd frontend
npm run build

The production build should complete successfully before deployment.

API verification

Swagger can be used to verify protected and operational endpoints:

http://127.0.0.1:8000/docs

Gemini quota considerations

Tutor, quiz generation, and assessment evaluation use the Gemini API and are subject to provider rate limits and quotas. Non-AI components such as authentication, project isolation, analytics, learning context, workflow processing, observability, evaluation, and frontend/backend build checks can be tested independently.

Documentation

Additional submission documentation is provided separately and can also be maintained under docs/:

Architecture Documentation

AI Tools & Usage Documentation

Development Prompts

Evaluation Approach

Known Limitations

Future Improvements

Current Prototype Limitations

PDF text extraction and chunking are implemented; advanced OCR for scanned documents is not the primary processing path.

Retrieval currently uses Project-scoped chunk search rather than a production-scale vector database.

Background workflows provide basic job states and failure handling; durable queue infrastructure and comprehensive distributed idempotency are future improvements.

AI evaluation is primarily rule-based and is not a replacement for a large curated benchmark or human review.

Production-scale monitoring, tracing, caching, and provider abstraction are not the primary prototype focus.

Future Improvements

Potential next improvements include:

Streaming Tutor responses

Rich document and OCR understanding

Vector/embedding retrieval

Improved analytics and concept trends

Persistent Tutor conversation continuity

Durable background job queues

Strong retry and idempotency mechanisms

AI tracing

Provider abstraction

Automated regression evaluation datasets

Caching

Spaced repetition and learning plans

Concept maps and additional learning experiences

Engineering Decisions

The prototype prioritizes a complete connected learning loop and clear separation of responsibilities over production-scale infrastructure. FastAPI provides a modular Python application layer, Next.js provides the interactive workspace, PostgreSQL provides persistent learning state, a worker handles document processing, and Gemini provides selected generation capabilities.

AI is treated as a controlled application component rather than an unrestricted database interface. Retrieval, context selection, authorization, structured validation, observability, and evaluation are handled by the application around the model.

Author

Nithin Rankireddy

AI Study Companion — Full Stack AI Engineer Candidate Project

License

This project was created as a candidate challenge prototype.
