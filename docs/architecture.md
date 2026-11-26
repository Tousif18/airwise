# AirWise Architecture & Data Integrity

## Separation of Concerns

- **Frontend (`frontend/`)**: React + Vite + Tailwind CSS + Recharts + Lucide icons. Communicates exclusively with the FastAPI backend over REST JSON (`/api/v1/*`) using `VITE_API_BASE_URL`. All AQI calculations happen in the backend.
- **Backend (`backend/`)**: Modular FastAPI application with strict Pydantic v2 contracts, environment-driven settings (`pydantic-settings`), and `httpx` async upstream integrations.

## Default Location & AQI Scales

- **Default Location**: **Kolkata, West Bengal, India** (`22.5726, 88.3639`, `Asia/Kolkata`), alongside quick-select urban hubs (New Delhi, Gurugram, Mumbai, Bengaluru, Lahore, London) and Open-Meteo Geocoding search.
- **Indian CPCB AQI (NAQI)**: Computed in [`backend/app/services/cpcb_aqi.py`](../backend/app/services/cpcb_aqi.py) via the prescribed CPCB segmented linear interpolation breakpoints over trailing 24-hour averages (`PM2.5`, `PM10`, `NO₂`, `SO₂`, minimum 16 valid hours) and trailing 8-hour averages (`O₃`, `CO` converted from `μg/m³` to `mg/m³`, minimum 6 valid hours). Enforces the CPCB requirement of at least 3 valid pollutants including at least one particulate metric (`PM2.5` or `PM10`). Never approximates Indian AQI from US AQI.
- **US AQI & European AQI**: Retained and clearly labelled from Open-Meteo (`US EPA Scale` and `EAQI`).

## Data Freshness, Value Kind & Warnings

- **Freshness (`data_status`)**: Explicitly distinguishes `live`, `cached`, and `unavailable`.
- **Value Kind (`value_kind`)**: Explicitly identifies `observed` (direct ground sensors, currently N/A from Open-Meteo), `estimated` (Open-Meteo CAMS atmospheric model current/past hours), and `forecast` (upcoming model hours).
- **Stale & API Warnings**: Flags `is_stale` when cached telemetry ages past `AIR_QUALITY_STALE_WARNING_SECONDS` or when a live refresh fails and falls back to expired cached telemetry (`api_warning` + `stale_reason`). When no valid data exists, returns `unavailable` with `null` readings.
- **Rate-Limit Resilience & Request Coalescing**: [`OpenMeteoAirQualityService`](../backend/app/services/open_meteo.py) and [`LocationSearchService`](../backend/app/services/locations.py) coalesce concurrent identical upstream calls (`AsyncRequestCoalescer`), cache responses by `(latitude, longitude, timezone)` / normalized city query, apply bounded exponential backoff with jitter while respecting `Retry-After` on HTTP `429`, and store a short-lived negative cooldown cache to prevent upstream request storms. The frontend pairs this with in-flight GET deduplication, debounced city search, and a manual refresh cooldown.

## Environment Variables

- `backend/.env`: `CORS_ORIGINS`, `OPEN_METEO_AIR_QUALITY_URL`, `OPEN_METEO_GEOCODING_URL`, `AIR_QUALITY_CACHE_TTL_SECONDS`, `AIR_QUALITY_STALE_WARNING_SECONDS`, `AIR_QUALITY_OBSERVATION_STALE_MINUTES`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`.
- `frontend/.env`: `VITE_API_BASE_URL`.

## Phase 2: AirWise AI Intelligence

### Deterministic Safety & Context Pipeline

1. **Decision Engine ([`backend/app/services/decision_engine.py`](../backend/app/services/decision_engine.py))**: Evaluates US AQI (EPA), European AQI (EAQI), and Indian CPCB AQI (NAQI) independently without mixing numeric scales or inventing missing CPCB readings. Applies family vulnerability escalation (children, older adults, respiratory sensitivity), identifies high-exposure activities, detects stale/missing data, and generates full rule-based fallback recommendations when Gemini is unavailable.
2. **Context Builder ([`backend/app/services/context_builder.py`](../backend/app/services/context_builder.py))**: Combines location, telemetry integrity, pollutant concentrations, separated AQI standards, family profile (excluding personal names and medical records), deterministic safety posture, and user question while explicitly tagging `observed`, `estimated`, `forecast`, and `missing` data.
3. **Gemini Service ([`backend/app/services/gemini_service.py`](../backend/app/services/gemini_service.py))**: Uses the official `google-genai` Python SDK on the backend only, enforces timeouts and structured JSON Pydantic output (`AssistantStructuredResponse`), validates against unsafe/prohibited claims (medical diagnoses, unsupported plant claims, 100% mask/purifier guarantees), and falls back cleanly to deterministic guidance if Gemini is unavailable or invalid.

### API Endpoints (`/api/v1`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service health & integration readiness (no secrets) |
| `GET` | `/api/v1/locations/presets` | Curated urban preset locations |
| `GET` | `/api/v1/locations/search` | Open-Meteo geocoding city search |
| `GET` | `/api/v1/air-quality` | Live/cached/unavailable Open-Meteo telemetry + CPCB AQI |
| `GET` | `/api/v1/family/profile` | Fetch household profile (also aliased at `/api/v1/family-profile`) |
| `PUT` | `/api/v1/family/profile` | Update household profile (also aliased at `/api/v1/family-profile`) |
| `GET` | `/api/v1/assistant/health` | Gemini readiness & deterministic fallback availability |
| `POST` | `/api/v1/assistant/chat` | Conversational air-quality Q&A returning structured JSON |
| `POST` | `/api/v1/assistant/recommendations` | Structured daily/focused family recommendations |
| `POST` | `/api/v1/indoor/recommendations` | Phase 3 Indoor Air Quality Advisor recommendations (user home profile + outdoor telemetry) |

## Phase 4: Environmental Impact Tracker

- Pure emission calculation, validation, and aggregation utilities live in [`frontend/src/utils/emissions.js`](../frontend/src/utils/emissions.js), unit-tested with Node's built-in test runner ([`frontend/tests/emissions.test.mjs`](../frontend/tests/emissions.test.mjs)).
- Users log public transport, carpooling, avoided private vehicle, and walking/cycling trips persisted in browser `localStorage` (`airwise_impact_records_v1` and `airwise_emission_assumptions_v1`), with configurable baseline car, transit, and carpool occupancy assumptions and clear disclosure that all CO₂ figures are modeled estimates rather than direct measurements.
