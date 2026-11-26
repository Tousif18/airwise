# AirWise

AI-powered Urban Air Quality Assistant built for the **Google Developers x Hack2Skill PromptWars Challenge 06**.

AirWise helps urban families and residential communities navigate winter smog and urban air pollution through transparent air-quality telemetry, household sensitivity profiles, indoor air protection guidance, and sustainable daily alternatives.

## Project Structure

```text
airwise/
├── backend/                  # Modular FastAPI backend
│   ├── app/
│   │   ├── api/              # Versioned API router and route handlers
│   │   ├── core/             # Environment settings & shared dependencies
│   │   ├── schemas/          # Pydantic v2 request/response models
│   │   ├── services/         # Open-Meteo client, TTL cache, Gemini placeholder
│   │   └── main.py           # FastAPI application entry point
│   ├── .env.example          # Environment variable template (no secrets)
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React + Vite + Tailwind CSS frontend
│   ├── src/
│   │   ├── components/       # Reusable UI components (layout, dashboard, feedback)
│   │   ├── pages/            # Dashboard & placeholder feature pages
│   │   ├── services/         # Typed HTTP fetch helpers for FastAPI
│   │   └── utils/            # AQI presentation & formatting helpers
│   ├── .env.example          # Frontend API base URL template
│   └── package.json          # Node dependencies & scripts
├── docs/                     # Architecture & engineering documentation
│   └── architecture.md
└── tests/                    # Automated backend API & service tests
    └── test_air_quality_api.py
```

## Quick Start

### 1. Backend (FastAPI)

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend (React + Vite)

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

### 3. Run Tests

```powershell
# Backend tests
cd backend
.\.venv\Scripts\python.exe -m pytest ..\tests -v

# Frontend emission calculation tests
cd ..\frontend
npm test
```

## Phase 2 AI Intelligence Endpoints

- `GET /api/v1/family/profile` & `PUT /api/v1/family/profile` — Household profile (backed by browser `localStorage` + FastAPI sync; excludes personal names and medical records).
- `GET /api/v1/assistant/health` — Reports Gemini SDK readiness and rule-based fallback availability without exposing credentials.
- `POST /api/v1/assistant/chat` — Grounded conversational Q&A combining Open-Meteo telemetry, separated AQI standards, deterministic decision rules, and Google Gemini (`google-genai`).
- `POST /api/v1/assistant/recommendations` — Structured household recommendations with priority labels, indoor/outdoor actions, sustainable alternatives, reasoning, and data limitations.
- `POST /api/v1/indoor/recommendations` — Phase 3 Indoor Air Quality Advisor combining user-provided home environment details with outdoor Open-Meteo telemetry (without fabricating indoor sensor readings).
