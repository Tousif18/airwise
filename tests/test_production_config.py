"""Production deployment configuration tests for Render & Vercel CORS."""

from pathlib import Path
import sys
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings, get_settings
from app.main import create_app


def test_settings_loads_from_os_environ_without_env_file(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("CORS_ORIGINS", "https://airwise.vercel.app/, http://localhost:5173")
    monkeypatch.setenv("FRONTEND_URL", "https://airwise-custom.vercel.app/")
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"^https://airwise-[a-z0-9-]+\.vercel\.app$")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    settings = Settings(_env_file="/nonexistent/path/.env")

    assert settings.app_env == "production"
    assert settings.backend_port == 10000
    assert settings.resolved_host == "0.0.0.0"
    assert settings.gemini_configured is False
    assert settings.cors_origins == [
        "https://airwise.vercel.app",
        "http://localhost:5173",
        "https://airwise-custom.vercel.app",
    ]
    assert settings.cors_origin_regex == r"^https://airwise-[a-z0-9-]+\.vercel\.app$"


def test_health_endpoints_work_without_gemini_api_key(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    try:
        prod_app = create_app()
        client = TestClient(prod_app)

        health_res = client.get("/api/v1/health")
        assert health_res.status_code == 200
        health_body = health_res.json()
        assert health_body["status"] == "ok"
        assert health_body["environment"] == "production"
        assert health_body["gemini_configured"] is False

        assistant_res = client.get("/api/v1/assistant/health")
        assert assistant_res.status_code == 200
        assistant_body = assistant_res.json()
        assert assistant_body["status"] == "ok"
        assert assistant_body["gemini_configured"] is False
        assert assistant_body["fallback_mode_available"] is True
    finally:
        get_settings.cache_clear()


def test_cors_accepts_vercel_origins_and_preview_regex(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://airwise.vercel.app/")
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"https://airwise-.*\.vercel\.app")
    get_settings.cache_clear()

    try:
        prod_app = create_app()
        client = TestClient(prod_app)

        prod_res = client.get(
            "/api/v1/health",
            headers={"Origin": "https://airwise.vercel.app"},
        )
        assert prod_res.status_code == 200
        assert prod_res.headers.get("access-control-allow-origin") == "https://airwise.vercel.app"

        preview_res = client.options(
            "/api/v1/assistant/chat",
            headers={
                "Origin": "https://airwise-git-main-user.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preview_res.status_code == 200
        assert (
            preview_res.headers.get("access-control-allow-origin")
            == "https://airwise-git-main-user.vercel.app"
        )
        assert preview_res.headers.get("access-control-allow-credentials") is None
        assert preview_res.headers.get("access-control-allow-methods") == "GET, POST, OPTIONS"
        assert preview_res.headers.get("access-control-allow-headers") == "Accept, Accept-Language, Content-Language, Content-Type"

        # Similar-looking or suffix-spoofed domains must not match the preview regex.
        spoofed_res = client.options(
            "/api/v1/assistant/chat",
            headers={
                "Origin": "https://airwise-preview.vercel.app.attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert spoofed_res.headers.get("access-control-allow-origin") is None

        # Empty CORS_ORIGIN_REGEX="" must become None and NOT allow arbitrary origins
        monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
        monkeypatch.setenv("CORS_ORIGINS", "https://airwise.vercel.app")
        get_settings.cache_clear()
        strict_app = create_app()
        strict_client = TestClient(strict_app)
        blocked_res = strict_client.get(
            "/api/v1/health",
            headers={"Origin": "https://untrusted.example.com"},
        )
        assert blocked_res.status_code == 200
        assert blocked_res.headers.get("access-control-allow-origin") is None
    finally:
        get_settings.cache_clear()



def test_liveness_and_readiness_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: Settings(
            open_meteo_air_quality_url="https://air-quality.example/api",
            open_meteo_geocoding_url="https://geocoding.example/search",
        ),
    )
    client = TestClient(create_app())

    live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"] == {
        "open_meteo_air_quality_url": True,
        "open_meteo_geocoding_url": True,
    }


def test_readiness_fails_for_invalid_required_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: Settings(
            open_meteo_air_quality_url="not-a-url",
            open_meteo_geocoding_url="https://geocoding.example/search",
        ),
    )
    client = TestClient(create_app())

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {
        "open_meteo_air_quality_url": False,
        "open_meteo_geocoding_url": True,
    }


def test_readiness_does_not_require_gemini_or_live_upstream_access(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: Settings(gemini_api_key=None),
    )
    client = TestClient(create_app())

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_render_uses_readiness_endpoint_for_deployment_health_checks() -> None:
    render_config = (Path(__file__).resolve().parents[1] / "render.yaml").read_text()
    assert "healthCheckPath: /api/v1/health/ready" in render_config
