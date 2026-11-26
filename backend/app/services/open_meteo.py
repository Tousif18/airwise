"""Open-Meteo Air Quality API client with CPCB AQI, coalescing, 429 backoff, and stale warnings."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import random
from typing import Any
import httpx

from app.core.config import Settings
from app.schemas.air_quality import (
    AirQualityOverviewResponse,
    DataStatus,
    HourlyTrendPoint,
    IndianAQISummary,
    LocationOption,
    PollutantReading,
    ValueKind,
)
from app.services.cache import AsyncRequestCoalescer, TTLCache
from app.services.cpcb_aqi import compute_cpcb_aqi_from_hourly

POLLUTANT_SPECS: list[dict[str, Any]] = [
    {
        "key": "pm2_5",
        "label": "Fine Particulate Matter",
        "formula": "PM2.5",
        "default_unit": "μg/m³",
        "guideline_24h": 15.0,
        "description": "Inhalable fine particles that penetrate deep into lungs during winter smog.",
    },
    {
        "key": "pm10",
        "label": "Coarse Particulate Matter",
        "formula": "PM10",
        "default_unit": "μg/m³",
        "guideline_24h": 45.0,
        "description": "Dust, smoke, and road particulates irritating airways.",
    },
    {
        "key": "nitrogen_dioxide",
        "label": "Nitrogen Dioxide",
        "formula": "NO₂",
        "default_unit": "μg/m³",
        "guideline_24h": 25.0,
        "description": "Traffic and combustion gas linked to respiratory inflammation.",
    },
    {
        "key": "ozone",
        "label": "Ground-Level Ozone",
        "formula": "O₃",
        "default_unit": "μg/m³",
        "guideline_24h": 100.0,
        "description": "Photochemical oxidant that triggers asthma and throat irritation.",
    },
    {
        "key": "sulphur_dioxide",
        "label": "Sulphur Dioxide",
        "formula": "SO₂",
        "default_unit": "μg/m³",
        "guideline_24h": 40.0,
        "description": "Fossil-fuel and industrial emission gas affecting sensitive airways.",
    },
    {
        "key": "carbon_monoxide",
        "label": "Carbon Monoxide",
        "formula": "CO",
        "default_unit": "μg/m³",
        "guideline_24h": 4000.0,
        "description": "Colorless combustion gas elevated near dense traffic and heating.",
    },
]


@dataclass(frozen=True)
class RateLimitState:
    """Negative-cache metadata stored when Open-Meteo returns HTTP 429."""

    retry_after_seconds: int
    reason: str


class OpenMeteoUpstreamError(Exception):
    """Structured error raised when Open-Meteo fetch fails after bounded retries."""

    def __init__(
        self,
        message: str,
        *,
        rate_limited: bool = False,
        retry_after_seconds: int | None = None,
        error_code: str = "upstream_unavailable",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.rate_limited = rate_limited
        self.retry_after_seconds = retry_after_seconds
        self.error_code = error_code


def parse_retry_after_seconds(header_value: str | None) -> int | None:
    """Parse HTTP Retry-After header (seconds or HTTP-date) into bounded integer seconds."""
    if not header_value:
        return None
    cleaned = header_value.strip()
    if not cleaned:
        return None
    try:
        numeric = float(cleaned)
        if math.isfinite(numeric):
            return max(1, min(3600, math.ceil(numeric)))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(cleaned)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delta = (target.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        return max(1, min(3600, math.ceil(delta)))
    except (TypeError, ValueError):
        return None


def classify_us_aqi(us_aqi: float | None) -> str:
    """Map US AQI numeric value to standard EPA category label."""
    if us_aqi is None:
        return "Unavailable"
    if us_aqi <= 50:
        return "Good"
    if us_aqi <= 100:
        return "Moderate"
    if us_aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if us_aqi <= 200:
        return "Unhealthy"
    if us_aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _build_unavailable_response(
    location: LocationOption,
    error_detail: str,
    *,
    rate_limited: bool = False,
    retry_after_seconds: int | None = None,
    error_code: str = "upstream_unavailable",
) -> AirQualityOverviewResponse:
    """Return an explicit unavailable response without fabricating any readings."""
    pollutants = [
        PollutantReading(
            key=spec["key"],
            label=spec["label"],
            formula=spec["formula"],
            value=None,
            unit=spec["default_unit"],
            status=DataStatus.UNAVAILABLE,
            value_kind=ValueKind.ESTIMATED,
            guideline_24h=spec["guideline_24h"],
            description=spec["description"],
        )
        for spec in POLLUTANT_SPECS
    ]
    return AirQualityOverviewResponse(
        location=location,
        data_status=DataStatus.UNAVAILABLE,
        telemetry_kind=ValueKind.ESTIMATED,
        observation_time=None,
        fetched_at=None,
        cached_at=None,
        cache_expires_at=None,
        is_stale=False,
        api_warning=error_detail,
        rate_limited=rate_limited,
        retry_after_seconds=retry_after_seconds,
        error_code=error_code,
        us_aqi=None,
        european_aqi=None,
        aqi_category="Unavailable",
        indian_aqi=IndianAQISummary(
            status=DataStatus.UNAVAILABLE,
            unavailable_reason="Indian CPCB AQI unavailable because Open-Meteo telemetry could not be retrieved.",
        ),
        pollutants=pollutants,
        hourly_trend=[],
        error_detail=error_detail,
    )


def _find_past_slice_end(times: list[Any], observation_time: str | None) -> int:
    """Return index immediately after the latest hourly slot <= observation_time."""
    if not times:
        return 0
    if not observation_time:
        return len(times)
    end_idx = 0
    for idx, ts in enumerate(times):
        if str(ts) <= observation_time:
            end_idx = idx + 1
        else:
            break
    return end_idx if end_idx > 0 else len(times)


def _parse_open_meteo_payload(
    payload: dict[str, Any],
    location: LocationOption,
    fetched_at: datetime,
) -> AirQualityOverviewResponse:
    """Transform Open-Meteo JSON into AirWise overview response with CPCB AQI."""
    current = payload.get("current") or {}
    current_units = payload.get("current_units") or {}
    hourly = payload.get("hourly") or {}

    observation_time = str(current["time"]) if current.get("time") else None
    us_aqi = _to_float_or_none(current.get("us_aqi"))
    european_aqi = _to_float_or_none(current.get("european_aqi"))

    times = [str(ts) for ts in (hourly.get("time") or [])]
    past_slice_end = _find_past_slice_end(times, observation_time)

    hourly_series: dict[str, list[float | None]] = {
        key: [_to_float_or_none(v) for v in (hourly.get(key) or [])]
        for key in (
            "pm2_5",
            "pm10",
            "nitrogen_dioxide",
            "ozone",
            "carbon_monoxide",
            "sulphur_dioxide",
        )
    }

    indian_aqi = compute_cpcb_aqi_from_hourly(
        hourly_series=hourly_series,
        past_slice_end=past_slice_end,
        data_status=DataStatus.LIVE,
        value_kind=ValueKind.ESTIMATED,
    )
    sub_index_map = {item.pollutant_key: item for item in indian_aqi.sub_indices}

    pollutants: list[PollutantReading] = []
    for spec in POLLUTANT_SPECS:
        key = spec["key"]
        val = _to_float_or_none(current.get(key))
        sub = sub_index_map.get(key)
        pollutants.append(
            PollutantReading(
                key=key,
                label=spec["label"],
                formula=spec["formula"],
                value=val,
                unit=current_units.get(key) or spec["default_unit"],
                status=DataStatus.LIVE if val is not None else DataStatus.UNAVAILABLE,
                value_kind=ValueKind.ESTIMATED,
                guideline_24h=spec["guideline_24h"],
                description=spec["description"],
                cpcb_sub_index=sub.sub_index if sub else None,
                cpcb_category=sub.category if sub else None,
                cpcb_avg_value=sub.concentration if sub else None,
                cpcb_avg_unit=sub.unit if sub else None,
                cpcb_averaging_period=sub.averaging_period if sub else None,
            )
        )

    hourly_aqi = hourly.get("us_aqi") or []
    hourly_pm25 = hourly.get("pm2_5") or []
    hourly_pm10 = hourly.get("pm10") or []

    chart_start = max(0, past_slice_end - 18) if times else 0
    chart_end = min(len(times), chart_start + 24)
    if chart_end - chart_start < 24 and len(times) > chart_end - chart_start:
        chart_start = max(0, len(times) - 24)
        chart_end = len(times)

    hourly_trend: list[HourlyTrendPoint] = []
    for idx in range(chart_start, chart_end):
        ts = times[idx]
        kind = (
            ValueKind.FORECAST
            if observation_time and ts > observation_time
            else ValueKind.ESTIMATED
        )
        hourly_trend.append(
            HourlyTrendPoint(
                time=ts,
                us_aqi=_to_float_or_none(hourly_aqi[idx]) if idx < len(hourly_aqi) else None,
                pm2_5=_to_float_or_none(hourly_pm25[idx]) if idx < len(hourly_pm25) else None,
                pm10=_to_float_or_none(hourly_pm10[idx]) if idx < len(hourly_pm10) else None,
                value_kind=kind,
            )
        )

    any_live = us_aqi is not None or any(p.value is not None for p in pollutants)
    overall_status = DataStatus.LIVE if any_live else DataStatus.UNAVAILABLE

    return AirQualityOverviewResponse(
        location=location,
        data_status=overall_status,
        telemetry_kind=ValueKind.ESTIMATED,
        observation_time=observation_time,
        fetched_at=fetched_at,
        us_aqi=us_aqi,
        european_aqi=european_aqi,
        aqi_category=classify_us_aqi(us_aqi),
        indian_aqi=indian_aqi
        if any_live
        else IndianAQISummary(
            status=DataStatus.UNAVAILABLE,
            unavailable_reason="Indian CPCB AQI unavailable: upstream returned empty sensor readings.",
        ),
        pollutants=pollutants,
        hourly_trend=hourly_trend,
        error_code=None if any_live else "empty_readings",
        error_detail=None if any_live else "Open-Meteo returned empty sensor readings for this location.",
    )


class OpenMeteoAirQualityService:
    """Service orchestrating live Open-Meteo fetches, coalescing, 429 backoff, and TTL caching."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: TTLCache[AirQualityOverviewResponse] = TTLCache(
            ttl_seconds=settings.air_quality_cache_ttl_seconds
        )
        self._rate_limit_cache: TTLCache[RateLimitState] = TTLCache(
            ttl_seconds=settings.air_quality_rate_limit_cooldown_seconds
        )
        self._coalescer: AsyncRequestCoalescer[AirQualityOverviewResponse] = (
            AsyncRequestCoalescer()
        )

    @staticmethod
    def _cache_key(location: LocationOption) -> str:
        tz = (location.timezone or "auto").strip()
        return f"{round(location.latitude, 4)}:{round(location.longitude, 4)}:{tz}"

    def _to_cached_response(
        self,
        entry: Any,
        location: LocationOption,
        is_expired_fallback: bool = False,
        api_warning: str | None = None,
        rate_limited: bool = False,
        retry_after_seconds: int | None = None,
        error_code: str | None = None,
    ) -> AirQualityOverviewResponse:
        now = datetime.now(timezone.utc)
        age_seconds = max(0, int((now - entry.cached_at).total_seconds()))
        is_stale = is_expired_fallback or (
            age_seconds >= self._settings.air_quality_stale_warning_seconds
        )
        stale_reason: str | None = None
        if is_expired_fallback:
            stale_reason = (
                f"Live refresh failed; displaying stale cached telemetry "
                f"({age_seconds // 60}m {age_seconds % 60}s old)."
            )
        elif is_stale:
            stale_reason = (
                f"Cached telemetry is {age_seconds // 60} min old. "
                "Use Refresh Live to request current conditions."
            )

        cached_pollutants = [
            p.model_copy(
                update={
                    "status": DataStatus.CACHED
                    if p.value is not None
                    else DataStatus.UNAVAILABLE
                }
            )
            for p in entry.value.pollutants
        ]
        cached_indian = entry.value.indian_aqi.model_copy(
            update={
                "status": DataStatus.CACHED
                if entry.value.indian_aqi.aqi is not None
                else DataStatus.UNAVAILABLE
            }
        )

        return entry.value.model_copy(
            update={
                "location": location,
                "data_status": DataStatus.CACHED,
                "cached_at": entry.cached_at,
                "cache_expires_at": entry.expires_at,
                "is_stale": is_stale,
                "stale_reason": stale_reason,
                "api_warning": api_warning,
                "rate_limited": rate_limited,
                "retry_after_seconds": retry_after_seconds,
                "error_code": error_code,
                "indian_aqi": cached_indian,
                "pollutants": cached_pollutants,
            }
        )

    def _compute_backoff_delay(
        self,
        attempt: int,
        retry_after_seconds: int | None = None,
    ) -> float:
        base = max(0.0, self._settings.air_quality_retry_base_delay_seconds)
        max_delay = max(base, self._settings.air_quality_retry_max_delay_seconds)
        exp_delay = base * (2 ** attempt)
        jitter = random.uniform(0.0, min(0.25, base * 0.5)) if base > 0 else 0.0
        target = exp_delay + jitter
        if retry_after_seconds is not None:
            target = max(target, float(retry_after_seconds))
        return min(max_delay, target)

    async def _fetch_payload_with_backoff(
        self,
        params: dict[str, Any],
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        owns_client = client is None
        active_client = client or httpx.AsyncClient(
            timeout=self._settings.http_timeout_seconds
        )
        max_retries = max(0, self._settings.air_quality_max_retries)
        max_delay = max(0.0, self._settings.air_quality_retry_max_delay_seconds)

        try:
            for attempt in range(max_retries + 1):
                try:
                    response = await active_client.get(
                        self._settings.open_meteo_air_quality_url,
                        params=params,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < max_retries:
                        await asyncio.sleep(self._compute_backoff_delay(attempt))
                        continue
                    raise OpenMeteoUpstreamError(
                        f"Unable to reach Open-Meteo Air Quality API: {exc}",
                        error_code="upstream_unreachable",
                    ) from exc

                status_code = response.status_code
                if status_code == 429:
                    retry_after = parse_retry_after_seconds(
                        response.headers.get("retry-after")
                    )
                    effective_retry_after = (
                        retry_after
                        or self._settings.air_quality_rate_limit_cooldown_seconds
                    )
                    # Retry only if Retry-After fits within bounded request retry delay
                    if (
                        attempt < max_retries
                        and (retry_after is None or retry_after <= max_delay)
                    ):
                        delay = self._compute_backoff_delay(
                            attempt,
                            retry_after_seconds=retry_after,
                        )
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue
                    raise OpenMeteoUpstreamError(
                        (
                            f"Open-Meteo Air Quality API rate limit reached (HTTP 429). "
                            f"Please wait about {effective_retry_after}s before retrying."
                        ),
                        rate_limited=True,
                        retry_after_seconds=effective_retry_after,
                        error_code="rate_limited",
                    )

                if status_code >= 500:
                    if attempt < max_retries:
                        await asyncio.sleep(self._compute_backoff_delay(attempt))
                        continue
                    raise OpenMeteoUpstreamError(
                        f"Open-Meteo Air Quality API returned HTTP {status_code}.",
                        error_code="upstream_server_error",
                    )

                if status_code >= 400:
                    raise OpenMeteoUpstreamError(
                        f"Open-Meteo Air Quality API returned HTTP {status_code}.",
                        error_code="upstream_client_error",
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    raise OpenMeteoUpstreamError(
                        f"Invalid JSON payload from Open-Meteo Air Quality API: {exc}",
                        error_code="invalid_upstream_payload",
                    ) from exc

            raise OpenMeteoUpstreamError(
                "Open-Meteo Air Quality API retries exhausted.",
                error_code="upstream_unavailable",
            )
        finally:
            if owns_client:
                await active_client.aclose()

    async def get_air_quality(
        self,
        location: LocationOption,
        force_refresh: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> AirQualityOverviewResponse:
        """Fetch live Open-Meteo data with coalescing, 429 cooldown, and stale fallback."""
        key = self._cache_key(location)

        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return self._to_cached_response(cached, location=location)

        # Negative rate-limit cache prevents request storms during active HTTP 429 cooldowns
        rate_entry = self._rate_limit_cache.get(key)
        if rate_entry is not None:
            now = datetime.now(timezone.utc)
            remaining = max(1, math.ceil((rate_entry.expires_at - now).total_seconds()))
            fallback_entry, _ = self._cache.get_with_staleness(key)
            warning = (
                f"{rate_entry.value.reason} (cooldown active: ~{remaining}s remaining)."
            )
            if fallback_entry is not None:
                return self._to_cached_response(
                    fallback_entry,
                    location=location,
                    is_expired_fallback=True,
                    api_warning=warning,
                    rate_limited=True,
                    retry_after_seconds=remaining,
                    error_code="rate_limited",
                )
            return _build_unavailable_response(
                location=location,
                error_detail=warning,
                rate_limited=True,
                retry_after_seconds=remaining,
                error_code="rate_limited",
            )

        async def _execute_fetch() -> AirQualityOverviewResponse:
            if not force_refresh:
                fresh = self._cache.get(key)
                if fresh is not None:
                    return self._to_cached_response(fresh, location=location)

            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": (
                    "us_aqi,european_aqi,pm10,pm2_5,carbon_monoxide,"
                    "nitrogen_dioxide,sulphur_dioxide,ozone"
                ),
                "hourly": (
                    "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
                    "sulphur_dioxide,ozone,us_aqi"
                ),
                "past_days": 1,
                "forecast_days": 1,
                "timezone": location.timezone or "auto",
            }

            try:
                payload = await self._fetch_payload_with_backoff(params, client=client)
            except OpenMeteoUpstreamError as exc:
                if exc.rate_limited:
                    cooldown = min(
                        3600,
                        max(
                            self._settings.air_quality_rate_limit_cooldown_seconds,
                            exc.retry_after_seconds or 0,
                        ),
                    )
                    self._rate_limit_cache.set(
                        key,
                        RateLimitState(
                            retry_after_seconds=cooldown,
                            reason=exc.message,
                        ),
                        ttl_seconds=cooldown,
                    )
                fallback_entry, _ = self._cache.get_with_staleness(key)
                if fallback_entry is not None:
                    return self._to_cached_response(
                        fallback_entry,
                        location=location,
                        is_expired_fallback=True,
                        api_warning=exc.message,
                        rate_limited=exc.rate_limited,
                        retry_after_seconds=exc.retry_after_seconds,
                        error_code=exc.error_code,
                    )
                return _build_unavailable_response(
                    location=location,
                    error_detail=exc.message,
                    rate_limited=exc.rate_limited,
                    retry_after_seconds=exc.retry_after_seconds,
                    error_code=exc.error_code,
                )

            fetched_at = datetime.now(timezone.utc)
            parsed = _parse_open_meteo_payload(
                payload, location=location, fetched_at=fetched_at
            )
            if parsed.data_status == DataStatus.LIVE:
                entry = self._cache.set(key, parsed)
                self._rate_limit_cache.delete(key)
                return parsed.model_copy(update={"cache_expires_at": entry.expires_at})
            return parsed

        return await self._coalescer.run(key, _execute_fetch)
