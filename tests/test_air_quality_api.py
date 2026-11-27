"""Automated tests for AirWise FastAPI endpoints and Open-Meteo freshness states."""

from datetime import datetime, timedelta, timezone
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
from app.schemas.air_quality import AirQualityOverviewResponse, DataStatus, LocationOption, ValueKind
from app.services.open_meteo import OpenMeteoAirQualityService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)



def test_air_quality_route_rejects_unknown_query_parameters(client: TestClient) -> None:
    response = client.get(
        "/api/v1/air-quality",
        params={"time_zone": "Asia/Kolkata"},
    )
    assert response.status_code == 422
    assert "Unknown query parameter" in response.json()["detail"]


def test_air_quality_route_accepts_known_query_parameters_and_keeps_default_location(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeService:
        async def get_air_quality(self, location: LocationOption, force_refresh: bool = False):
            return AirQualityOverviewResponse(
                location=location,
                data_status=DataStatus.UNAVAILABLE,
                pollutants=[],
            )

    monkeypatch.setattr(
        "app.api.routes.air_quality.get_air_quality_service",
        lambda: FakeService(),
    )
    response = client.get(
        "/api/v1/air-quality",
        params={"timezone": "Asia/Kolkata", "force_refresh": "false"},
    )
    assert response.status_code == 200
    assert response.json()["location"]["id"] == "kolkata-in"
    assert response.json()["location"]["timezone"] == "Asia/Kolkata"


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["open_meteo_configured"] is True
    assert isinstance(body["gemini_configured"], bool)


def test_preset_locations_default_is_kolkata(client: TestClient) -> None:
    response = client.get("/api/v1/locations/presets")
    assert response.status_code == 200
    body = response.json()
    assert len(body["locations"]) >= 5
    default_loc = body["locations"][0]
    assert default_loc["id"] == "kolkata-in"
    assert default_loc["name"] == "Kolkata"
    assert default_loc["country"] == "India"
    names = [loc["name"] for loc in body["locations"]]
    assert "New Delhi" in names


def test_family_profile_is_not_shared_through_legacy_api(client: TestClient) -> None:
    path = "/api/v1/family-profile"
    assert client.get(path).status_code == 404
    assert client.put(path, json={"city": "Kolkata"}).status_code == 404


@pytest.mark.asyncio
async def test_open_meteo_live_cached_cpcb_and_forecast_tagging() -> None:
    # 24 past/current hours (00:00..23:00 day 1) + 2 forecast hours (day 2)
    times = [f"2026-11-25T{h:02d}:00" for h in range(24)] + [
        "2026-11-26T00:00",
        "2026-11-26T01:00",
    ]
    sample_payload = {
        "current_units": {"pm2_5": "μg/m³", "pm10": "μg/m³", "carbon_monoxide": "μg/m³"},
        "current": {
            "time": "2026-11-25T23:30",
            "us_aqi": 168,
            "european_aqi": 92,
            "pm2_5": 90.0,
            "pm10": 150.0,
            "nitrogen_dioxide": 40.0,
            "ozone": 50.0,
            "sulphur_dioxide": 20.0,
            "carbon_monoxide": 1000.0,
        },
        "hourly": {
            "time": times,
            "us_aqi": [160] * 24 + [172, 175],
            "pm2_5": [90.0] * 24 + [95.0, 98.0],
            "pm10": [150.0] * 24 + [155.0, 160.0],
            "nitrogen_dioxide": [40.0] * 26,
            "ozone": [50.0] * 26,
            "sulphur_dioxide": [20.0] * 26,
            "carbon_monoxide": [1000.0] * 26,
        },
    }

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(handler)
    service = OpenMeteoAirQualityService(
        Settings(air_quality_cache_ttl_seconds=300, air_quality_stale_warning_seconds=300)
    )
    loc = LocationOption(
        id="kolkata-in",
        name="Kolkata",
        region="West Bengal",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
        timezone="Asia/Kolkata",
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        first = await service.get_air_quality(loc, client=http_client)
        second = await service.get_air_quality(loc, client=http_client)
        forced = await service.get_air_quality(loc, force_refresh=True, client=http_client)

    assert calls == 2
    assert first.data_status == DataStatus.LIVE
    assert first.telemetry_kind == ValueKind.ESTIMATED
    assert first.observation_time == "2026-11-25T23:30"
    assert first.us_aqi == 168.0
    assert first.aqi_category == "Unhealthy"

    # Indian CPCB AQI computed independently from trailing 24h/8h concentrations
    assert first.indian_aqi.status == DataStatus.LIVE
    assert first.indian_aqi.aqi == 200
    assert first.indian_aqi.category == "Moderate"
    assert first.indian_aqi.prominent_pollutant == "PM2.5"

    # Forecast vs Estimated classification on hourly trajectory
    estimated_pts = [pt for pt in first.hourly_trend if pt.value_kind == ValueKind.ESTIMATED]
    forecast_pts = [pt for pt in first.hourly_trend if pt.value_kind == ValueKind.FORECAST]
    assert len(estimated_pts) >= 1
    assert len(forecast_pts) == 2

    assert second.data_status == DataStatus.CACHED
    assert second.indian_aqi.status == DataStatus.CACHED
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
        id="kolkata-in",
        name="Kolkata",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        result = await service.get_air_quality(loc, client=http_client)

    assert result.data_status == DataStatus.UNAVAILABLE
    assert result.us_aqi is None
    assert result.european_aqi is None
    assert result.aqi_category == "Unavailable"
    assert result.indian_aqi.status == DataStatus.UNAVAILABLE
    assert result.indian_aqi.aqi is None
    assert result.hourly_trend == []
    assert all(p.value is None and p.status == DataStatus.UNAVAILABLE for p in result.pollutants)
    assert result.api_warning is not None


@pytest.mark.asyncio
async def test_stale_fallback_warning_when_live_refresh_fails() -> None:
    sample_payload = {
        "current": {
            "time": "2026-11-26T10:00",
            "us_aqi": 140,
            "european_aqi": 70,
            "pm2_5": 55.0,
        },
        "hourly": {"time": ["2026-11-26T10:00"], "us_aqi": [140], "pm2_5": [55.0]},
    }
    should_fail = False

    def handler(request: httpx.Request) -> httpx.Response:
        if should_fail:
            return httpx.Response(503, json={"error": "timeout"})
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(handler)
    service = OpenMeteoAirQualityService(
        Settings(air_quality_cache_ttl_seconds=600, air_quality_stale_warning_seconds=1)
    )
    loc = LocationOption(
        id="kolkata-in",
        name="Kolkata",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        live_res = await service.get_air_quality(loc, client=http_client)
        assert live_res.data_status == DataStatus.LIVE
        # Wait/backdate cached entry to simulate expired cache + API failure
        key = service._cache_key(loc)
        entry = service._cache._store[key]
        entry.cached_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        should_fail = True
        fallback_res = await service.get_air_quality(loc, force_refresh=True, client=http_client)

    assert fallback_res.data_status == DataStatus.CACHED
    assert fallback_res.is_stale is True
    assert fallback_res.stale_reason is not None
    assert fallback_res.api_warning is not None
    # Insufficient hourly points -> Indian CPCB AQI stays honestly Unavailable
    assert fallback_res.indian_aqi.status == DataStatus.UNAVAILABLE
    assert fallback_res.indian_aqi.aqi is None
