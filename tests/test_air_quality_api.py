"""Automated tests for AirWise FastAPI endpoints and Open-Meteo freshness states."""

from pathlib import Path
import sys
import httpx
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.main import app
from app.schemas.air_quality import DataStatus, LocationOption
from app.services.open_meteo import OpenMeteoAirQualityService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["open_meteo_configured"] is True
    assert isinstance(body["gemini_configured"], bool)


def test_preset_locations_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/locations/presets")
    assert response.status_code == 200
    body = response.json()
    assert len(body["locations"]) >= 4
    assert body["locations"][0]["name"] == "New Delhi"


def test_family_profile_roundtrip(client: TestClient) -> None:
    get_res = client.get("/api/v1/family-profile")
    assert get_res.status_code == 200
    original = get_res.json()

    updated_payload = {
        **original,
        "household_name": "Sharma Family",
        "member_count": 5,
        "has_respiratory_condition": True,
        "sensitivity_level": "high",
    }
    put_res = client.put("/api/v1/family-profile", json=updated_payload)
    assert put_res.status_code == 200
    saved = put_res.json()
    assert saved["household_name"] == "Sharma Family"
    assert saved["sensitivity_level"] == "high"


@pytest.mark.asyncio
async def test_open_meteo_live_then_cached_state() -> None:
    sample_payload = {
        "current_units": {"pm2_5": "μg/m³", "pm10": "μg/m³"},
        "current": {
            "us_aqi": 168,
            "european_aqi": 92,
            "pm2_5": 84.5,
            "pm10": 142.0,
            "nitrogen_dioxide": 38.2,
            "ozone": 24.0,
            "sulphur_dioxide": 11.4,
            "carbon_monoxide": 910.0,
        },
        "hourly": {
            "time": ["2026-11-26T00:00", "2026-11-26T01:00"],
            "us_aqi": [160, 168],
            "pm2_5": [80.0, 84.5],
            "pm10": [135.0, 142.0],
        },
    }

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(handler)
    service = OpenMeteoAirQualityService(Settings(air_quality_cache_ttl_seconds=300))
    loc = LocationOption(
        id="test-city",
        name="Test City",
        country="IN",
        latitude=28.61,
        longitude=77.21,
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        first = await service.get_air_quality(loc, client=http_client)
        second = await service.get_air_quality(loc, client=http_client)
        forced = await service.get_air_quality(loc, force_refresh=True, client=http_client)

    assert calls == 2
    assert first.data_status == DataStatus.LIVE
    assert first.us_aqi == 168.0
    assert first.aqi_category == "Unhealthy"

    assert second.data_status == DataStatus.CACHED
    assert second.cached_at is not None
    assert all(p.status == DataStatus.CACHED for p in second.pollutants)

    assert forced.data_status == DataStatus.LIVE


@pytest.mark.asyncio
async def test_open_meteo_unavailable_never_fakes_readings() -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream down"})

    transport = httpx.MockTransport(failing_handler)
    service = OpenMeteoAirQualityService(Settings())
    loc = LocationOption(
        id="test-city",
        name="Test City",
        country="IN",
        latitude=28.61,
        longitude=77.21,
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        result = await service.get_air_quality(loc, client=http_client)

    assert result.data_status == DataStatus.UNAVAILABLE
    assert result.us_aqi is None
    assert result.european_aqi is None
    assert result.aqi_category == "Unavailable"
    assert result.hourly_trend == []
    assert all(p.value is None and p.status == DataStatus.UNAVAILABLE for p in result.pollutants)
    assert result.error_detail is not None
