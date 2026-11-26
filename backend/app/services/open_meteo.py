"""Open-Meteo Air Quality API client with explicit live/cached/unavailable states."""

from datetime import datetime, timezone
from typing import Any
import httpx

from app.core.config import Settings
from app.schemas.air_quality import (
    AirQualityOverviewResponse,
    DataStatus,
    HourlyTrendPoint,
    LocationOption,
    PollutantReading,
)
from app.services.cache import TTLCache

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
            guideline_24h=spec["guideline_24h"],
            description=spec["description"],
        )
        for spec in POLLUTANT_SPECS
    ]
    return AirQualityOverviewResponse(
        location=location,
        data_status=DataStatus.UNAVAILABLE,
        fetched_at=None,
        cached_at=None,
        cache_expires_at=None,
        us_aqi=None,
        european_aqi=None,
        aqi_category="Unavailable",
        pollutants=pollutants,
        hourly_trend=[],
        error_detail=error_detail,
    )


def _parse_open_meteo_payload(
    payload: dict[str, Any],
    location: LocationOption,
    fetched_at: datetime,
) -> AirQualityOverviewResponse:
    """Transform Open-Meteo JSON into AirWise overview response."""
    current = payload.get("current") or {}
    current_units = payload.get("current_units") or {}
    hourly = payload.get("hourly") or {}

    us_aqi = _to_float_or_none(current.get("us_aqi"))
    european_aqi = _to_float_or_none(current.get("european_aqi"))

    pollutants: list[PollutantReading] = []
    for spec in POLLUTANT_SPECS:
        key = spec["key"]
        val = _to_float_or_none(current.get(key))
        pollutants.append(
            PollutantReading(
                key=key,
                label=spec["label"],
                formula=spec["formula"],
                value=val,
                unit=current_units.get(key) or spec["default_unit"],
                status=DataStatus.LIVE if val is not None else DataStatus.UNAVAILABLE,
                guideline_24h=spec["guideline_24h"],
                description=spec["description"],
            )
        )

    times = hourly.get("time") or []
    hourly_aqi = hourly.get("us_aqi") or []
    hourly_pm25 = hourly.get("pm2_5") or []
    hourly_pm10 = hourly.get("pm10") or []

    hourly_trend: list[HourlyTrendPoint] = []
    for idx, timestamp in enumerate(times[:24]):
        hourly_trend.append(
            HourlyTrendPoint(
                time=str(timestamp),
                us_aqi=_to_float_or_none(hourly_aqi[idx]) if idx < len(hourly_aqi) else None,
                pm2_5=_to_float_or_none(hourly_pm25[idx]) if idx < len(hourly_pm25) else None,
                pm10=_to_float_or_none(hourly_pm10[idx]) if idx < len(hourly_pm10) else None,
            )
        )

    any_live = us_aqi is not None or any(p.value is not None for p in pollutants)
    overall_status = DataStatus.LIVE if any_live else DataStatus.UNAVAILABLE

    return AirQualityOverviewResponse(
        location=location,
        data_status=overall_status,
        fetched_at=fetched_at,
        us_aqi=us_aqi,
        european_aqi=european_aqi,
        aqi_category=classify_us_aqi(us_aqi),
        pollutants=pollutants,
        hourly_trend=hourly_trend,
        error_detail=None if any_live else "Open-Meteo returned empty sensor readings for this location.",
    )


class OpenMeteoAirQualityService:
    """Service orchestrating live Open-Meteo fetches and TTL caching."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: TTLCache[AirQualityOverviewResponse] = TTLCache(
            ttl_seconds=settings.air_quality_cache_ttl_seconds
        )

    @staticmethod
    def _cache_key(location: LocationOption) -> str:
        return f"{round(location.latitude, 4)}:{round(location.longitude, 4)}"

    async def get_air_quality(
        self,
        location: LocationOption,
        force_refresh: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> AirQualityOverviewResponse:
        """Fetch live Open-Meteo data or return explicitly tagged cached/unavailable state."""
        key = self._cache_key(location)

        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                cached_pollutants = [
                    p.model_copy(
                        update={
                            "status": DataStatus.CACHED
                            if p.value is not None
                            else DataStatus.UNAVAILABLE
                        }
                    )
                    for p in cached.value.pollutants
                ]
                return cached.value.model_copy(
                    update={
                        "location": location,
                        "data_status": DataStatus.CACHED,
                        "cached_at": cached.cached_at,
                        "cache_expires_at": cached.expires_at,
                        "pollutants": cached_pollutants,
                    }
                )

        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": (
                "us_aqi,european_aqi,pm10,pm2_5,carbon_monoxide,"
                "nitrogen_dioxide,sulphur_dioxide,ozone"
            ),
            "hourly": "pm10,pm2_5,us_aqi",
            "forecast_days": 1,
            "timezone": location.timezone or "auto",
        }

        owns_client = client is None
        active_client = client or httpx.AsyncClient(
            timeout=self._settings.http_timeout_seconds
        )
        try:
            response = await active_client.get(
                self._settings.open_meteo_air_quality_url,
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return _build_unavailable_response(
                location=location,
                error_detail=f"Unable to reach Open-Meteo Air Quality API: {exc}",
            )
        finally:
            if owns_client:
                await active_client.aclose()

        fetched_at = datetime.now(timezone.utc)
        parsed = _parse_open_meteo_payload(payload, location=location, fetched_at=fetched_at)
        if parsed.data_status == DataStatus.LIVE:
            entry = self._cache.set(key, parsed)
            return parsed.model_copy(
                update={"cache_expires_at": entry.expires_at}
            )
        return parsed
