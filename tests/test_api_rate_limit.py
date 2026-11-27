"""Tests for application-level inbound API rate limiting."""

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.middleware.rate_limit import RateLimitMiddleware


def _client(settings: Settings) -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings)

    @app.post("/api/v1/assistant/chat")
    async def assistant_chat():
        return {"ok": True}

    @app.get("/api/v1/locations/search")
    async def location_search():
        return {"ok": True}

    @app.get("/api/v1/air-quality")
    async def air_quality():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True}

    return TestClient(app)


def test_ai_endpoint_returns_429_and_retry_after() -> None:
    client = _client(Settings(rate_limit_ai_per_minute=2))
    assert client.post("/api/v1/assistant/chat").status_code == 200
    assert client.post("/api/v1/assistant/chat").status_code == 200

    limited = client.post("/api/v1/assistant/chat")
    assert limited.status_code == 429
    assert limited.json()["error_code"] == "rate_limit_exceeded"
    assert int(limited.headers["Retry-After"]) >= 1
    assert limited.json()["retry_after_seconds"] >= 1


def test_forwarded_for_header_is_not_trusted_by_default() -> None:
    client = _client(Settings(rate_limit_search_per_minute=1))
    first = client.get("/api/v1/locations/search", headers={"X-Forwarded-For": "198.51.100.1"})
    second = client.get("/api/v1/locations/search", headers={"X-Forwarded-For": "198.51.100.2"})
    assert first.status_code == 200
    assert second.status_code == 429


def test_force_refresh_has_a_stricter_additional_limit() -> None:
    client = _client(
        Settings(
            rate_limit_air_quality_per_minute=5,
            rate_limit_force_refresh_per_minute=1,
        )
    )
    assert client.get("/api/v1/air-quality").status_code == 200
    assert client.get("/api/v1/air-quality?force_refresh=true").status_code == 200
    limited = client.get("/api/v1/air-quality?force_refresh=true")
    assert limited.status_code == 429
    assert client.get("/api/v1/air-quality").status_code == 200


def test_health_endpoint_is_not_rate_limited() -> None:
    client = _client(Settings(rate_limit_ai_per_minute=1))
    for _ in range(3):
        assert client.get("/api/v1/health").status_code == 200
