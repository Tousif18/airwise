# AirWise Architecture & Data Integrity

## Separation of Concerns

- **Frontend (`frontend/`)**: React + Vite + Tailwind CSS + Recharts + Lucide icons. Communicates exclusively with the FastAPI backend over REST JSON (`/api/v1/*`) using `VITE_API_BASE_URL`.
- **Backend (`backend/`)**: Modular FastAPI application with strict Pydantic v2 contracts, environment-driven settings (`pydantic-settings`), and `httpx` async upstream integrations.

## Data Freshness & Honesty Contract

AirWise never fabricates live AQI readings. Every air-quality response carries an explicit `data_status`:

1. `live`: Freshly fetched from the Open-Meteo Air Quality API, with `fetched_at` UTC timestamp.
2. `cached`: Returned from the in-memory TTL cache (`AIR_QUALITY_CACHE_TTL_SECONDS`, default 600s), with `cached_at` and `cache_expires_at`.
3. `unavailable`: Returned when Open-Meteo is unreachable or returns empty sensor values. All numeric pollutant and AQI fields remain `null` and `error_detail` surfaces the failure cleanly to the UI.

## Environment Variables

- `backend/.env`: `CORS_ORIGINS`, `OPEN_METEO_AIR_QUALITY_URL`, `OPEN_METEO_GEOCODING_URL`, `AIR_QUALITY_CACHE_TTL_SECONDS`, `GEMINI_API_KEY`, `GEMINI_MODEL`.
- `frontend/.env`: `VITE_API_BASE_URL`.
