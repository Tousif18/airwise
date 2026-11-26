"""Tests for Open-Meteo caching, request coalescing, HTTP 429 handling, Retry-After, and backoff."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.schemas.air_quality import DataStatus, LocationOption
from app.services.locations import LocationSearchService
from app.services.open_meteo import OpenMeteoAirQualityService, parse_retry_after_seconds


def _kolkata(tz: str = "Asia/Kolkata") -> LocationOption:
    return LocationOption(
        id="kolkata-in",
        name="Kolkata",
        region="West Bengal",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
        timezone=tz,
    )


def _sample_payload(us_aqi: int = 155) -> dict:
    return {
        "current": {
            "time": "2026-11-27T02:00",
            "us_aqi": us_aqi,
            "european_aqi": 68,
            "pm2_5": 65.0,
            "pm10": 110.0,
            "nitrogen_dioxide": 38.0,
            "ozone": 42.0,
            "sulphur_dioxide": 18.0,
            "carbon_monoxide": 900.0,
        },
        "hourly": {
            "time": ["2026-11-27T02:00"],
            "us_aqi": [us_aqi],
            "pm2_5": [65.0],
            "pm10": [110.0],
            "nitrogen_dioxide": [38.0],
            "ozone": [42.0],
            "sulphur_dioxide": [18.0],
            "carbon_monoxide": [900.0],
        },
    }


def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after_seconds("45") == 45
    assert parse_retry_after_seconds("0") == 1
    assert parse_retry_after_seconds("9999") == 3600
    assert parse_retry_after_seconds("not-a-date") is None
    assert parse_retry_after_seconds(None) is None


@pytest.mark.asyncio
async def test_cache_hit_expiry_and_timezone_key_isolation() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_sample_payload(150 + calls))

    service = OpenMeteoAirQualityService(
        Settings(air_quality_cache_ttl_seconds=600, air_quality_retry_base_delay_seconds=0.0)
    )
    loc_ist = _kolkata("Asia/Kolkata")
    loc_utc = _kolkata("UTC")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await service.get_air_quality(loc_ist, client=client)
        second = await service.get_air_quality(loc_ist, client=client)
        # Different timezone uses distinct cache key
        utc_res = await service.get_air_quality(loc_utc, client=client)

        assert calls == 2
        assert first.data_status == DataStatus.LIVE
        assert second.data_status == DataStatus.CACHED
        assert utc_res.data_status == DataStatus.LIVE

        # Expire IST cache entry -> triggers refresh
        ist_key = service._cache_key(loc_ist)
        service._cache._store[ist_key].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        refreshed = await service.get_air_quality(loc_ist, client=client)
        assert calls == 3
        assert refreshed.data_status == DataStatus.LIVE


@pytest.mark.asyncio
async def test_concurrent_identical_requests_coalesce_to_single_upstream_call() -> None:
    calls = 0

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=_sample_payload(170))

    service = OpenMeteoAirQualityService(Settings(air_quality_cache_ttl_seconds=600))
    loc = _kolkata()

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow_handler)) as client:
        results = await asyncio.gather(
            *[service.get_air_quality(loc, client=client) for _ in range(5)]
        )

    assert calls == 1
    assert all(res.us_aqi == 170.0 for res in results)


@pytest.mark.asyncio
async def test_http_429_respects_retry_after_and_bounded_backoff() -> None:
    attempts = 0

    def handler_recovers(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"reason": "slow down"})
        return httpx.Response(200, json=_sample_payload(140))

    service = OpenMeteoAirQualityService(
        Settings(
            air_quality_max_retries=2,
            air_quality_retry_base_delay_seconds=0.01,
            air_quality_retry_max_delay_seconds=1.2,
        )
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_recovers)) as client:
        res = await service.get_air_quality(_kolkata(), client=client)

    assert attempts == 2
    assert res.data_status == DataStatus.LIVE
    assert res.rate_limited is False


@pytest.mark.asyncio
async def test_http_429_large_retry_after_triggers_negative_cache_and_no_cache_unavailable() -> None:
    calls = 0

    def always_429(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "45"}, json={"error": "rate limit"})

    service = OpenMeteoAirQualityService(
        Settings(
            air_quality_max_retries=2,
            air_quality_retry_base_delay_seconds=0.01,
            air_quality_retry_max_delay_seconds=2.0,
            air_quality_rate_limit_cooldown_seconds=60,
        )
    )
    loc = _kolkata()

    async with httpx.AsyncClient(transport=httpx.MockTransport(always_429)) as client:
        first = await service.get_air_quality(loc, client=client)
        # Immediate follow-up (even with force_refresh=True) must hit negative cache, NOT upstream!
        second = await service.get_air_quality(loc, force_refresh=True, client=client)

    assert calls == 1  # Did not sleep 45s or hammer upstream
    assert first.data_status == DataStatus.UNAVAILABLE
    assert first.rate_limited is True
    assert first.retry_after_seconds is not None and first.retry_after_seconds >= 45
    assert first.error_code == "rate_limited"
    assert first.us_aqi is None

    assert second.data_status == DataStatus.UNAVAILABLE
    assert second.rate_limited is True
    assert "cooldown active" in (second.error_detail or "").lower()


@pytest.mark.asyncio
async def test_http_429_falls_back_to_stale_cached_data_with_original_timestamps() -> None:
    should_rate_limit = False
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if should_rate_limit:
            return httpx.Response(429, headers={"Retry-After": "30"})
        return httpx.Response(200, json=_sample_payload(188))

    service = OpenMeteoAirQualityService(
        Settings(
            air_quality_cache_ttl_seconds=600,
            air_quality_stale_warning_seconds=300,
            air_quality_max_retries=1,
            air_quality_retry_base_delay_seconds=0.01,
            air_quality_retry_max_delay_seconds=2.0,
            air_quality_rate_limit_cooldown_seconds=30,
        )
    )
    loc = _kolkata()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        live = await service.get_air_quality(loc, client=client)
        assert live.data_status == DataStatus.LIVE

        # Backdate cache entry to simulate expired cache
        key = service._cache_key(loc)
        entry = service._cache._store[key]
        entry.cached_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        should_rate_limit = True
        fallback = await service.get_air_quality(loc, client=client)

    assert fallback.data_status == DataStatus.CACHED
    assert fallback.is_stale is True
    assert fallback.rate_limited is True
    assert fallback.retry_after_seconds == 30
    assert fallback.error_code == "rate_limited"
    assert fallback.us_aqi == 188.0
    assert fallback.observation_time == "2026-11-27T02:00"
    assert fallback.stale_reason is not None


@pytest.mark.asyncio
async def test_geocoding_caching_coalescing_and_429_protection() -> None:
    calls = 0

    async def geo_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if "ratelimited" in str(request.url):
            return httpx.Response(429, headers={"Retry-After": "25"})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1275339,
                        "name": "Mumbai",
                        "admin1": "Maharashtra",
                        "country": "India",
                        "latitude": 19.076,
                        "longitude": 72.8777,
                        "timezone": "Asia/Kolkata",
                    }
                ]
            },
        )

    service = LocationSearchService(
        Settings(
            geocoding_cache_ttl_seconds=3600,
            air_quality_max_retries=1,
            air_quality_retry_max_delay_seconds=2.0,
            air_quality_rate_limit_cooldown_seconds=25,
        )
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(geo_handler)) as client:
        r1, r2 = await asyncio.gather(
            service.search("Mumbai", client=client),
            service.search("mumbai", client=client),
        )
        r3 = await service.search("  MUMBAI ", client=client)

        assert calls == 1
        assert len(r1.locations) == 1
        assert r3.data_status == DataStatus.CACHED

        limited = await service.search("ratelimited", client=client)
        assert limited.data_status == DataStatus.UNAVAILABLE
        assert limited.rate_limited is True
        assert limited.retry_after_seconds == 25
