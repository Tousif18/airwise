"""Tests for inbound request-size limits on AI endpoints."""

from pathlib import Path
import sys

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.middleware.request_size_limit import RequestSizeLimitMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware)

    @app.post("/api/v1/assistant/chat")
    async def chat(request: Request):
        body = await request.json()
        return {"question_length": len(body.get("question", ""))}

    @app.post("/api/v1/assistant/recommendations")
    async def recommendations():
        return {"ok": True}

    @app.post("/api/v1/indoor/recommendations")
    async def indoor():
        return {"ok": True}

    @app.post("/api/v1/other")
    async def other():
        return {"ok": True}

    return TestClient(app)


def test_ai_endpoint_accepts_request_within_64_kb_limit() -> None:
    response = _client().post(
        "/api/v1/assistant/chat",
        json={"question": "a" * 1000},
    )
    assert response.status_code == 200
    assert response.json()["question_length"] == 1000


def test_ai_endpoints_reject_oversized_request_bodies() -> None:
    client = _client()
    oversized = b'{"question":"' + (b"a" * (64 * 1024)) + b'"}'
    for path in (
        "/api/v1/assistant/chat",
        "/api/v1/assistant/recommendations",
        "/api/v1/indoor/recommendations",
    ):
        response = client.post(
            path,
            content=oversized,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error_code"] == "request_body_too_large"


def test_request_size_limit_does_not_change_other_endpoints() -> None:
    response = _client().post(
        "/api/v1/other",
        content=b"x" * (70 * 1024),
    )
    assert response.status_code == 200
