"""Pydantic schemas for air quality, locations, CPCB AQI, and data freshness state."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator\n\nfrom app.schemas.location_validation import validate_coordinate


class DataStatus(str, Enum):
    """Explicit indicator distinguishing live, cached, and unavailable readings."""

    LIVE = "live"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"


class ValueKind(str, Enum):
    """Distinguishes direct ground observations, atmospheric model estimates, and forecasts."""

    OBSERVED = "observed"
    ESTIMATED = "estimated"
    FORECAST = "forecast"


class LocationOption(BaseModel):
    """Geographic location metadata used for Open-Meteo queries."""

    id: str
    name: str
    region: str = ""
    country: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str = "auto"


class CPCBSubIndex(BaseModel):
    """Pollutant-specific Indian CPCB National AQI sub-index result."""

    pollutant_key: str
    formula: str
    concentration: float
    unit: str
    averaging_period: str
    valid_hours: int
    required_hours: int
    sub_index: int
    category: str


class IndianAQISummary(BaseModel):
    """Composite Indian CPCB AQI calculated from valid pollutant sub-indices."""

    aqi: int | None = None
    category: str = "Unavailable"
    status: DataStatus = DataStatus.UNAVAILABLE
    prominent_pollutant: str | None = None
    prominent_pollutant_key: str | None = None
    valid_pollutant_count: int = 0
    sub_indices: list[CPCBSubIndex] = Field(default_factory=list)
    value_kind: ValueKind = ValueKind.ESTIMATED
    methodology_note: str = (
        "Calculated via Indian CPCB NAQI breakpoint interpolation over trailing "
        "24h/8h modeled concentrations from Open-Meteo (not an official CPCB station feed)."
    )
    unavailable_reason: str | None = None


class PollutantReading(BaseModel):
    """Single pollutant measurement with guideline context, CPCB sub-index, and freshness."""

    key: str
    label: str
    formula: str
    value: float | None = None
    unit: str
    status: DataStatus
    value_kind: ValueKind = ValueKind.ESTIMATED
    guideline_24h: float | None = None
    description: str
    cpcb_sub_index: int | None = None
    cpcb_category: str | None = None
    cpcb_avg_value: float | None = None
    cpcb_avg_unit: str | None = None
    cpcb_averaging_period: str | None = None


class HourlyTrendPoint(BaseModel):
    """Hourly air quality trend point returned by Open-Meteo."""

    time: str
    us_aqi: float | None = None
    pm2_5: float | None = None
    pm10: float | None = None
    value_kind: ValueKind = ValueKind.ESTIMATED


class AirQualityOverviewResponse(BaseModel):
    """Full air quality payload for a selected location."""

    location: LocationOption
    data_status: DataStatus
    telemetry_kind: ValueKind = ValueKind.ESTIMATED
    source: str = "Open-Meteo Air Quality API (CAMS atmospheric model)"
    observation_time: str | None = None
    fetched_at: datetime | None = None
    cached_at: datetime | None = None
    cache_expires_at: datetime | None = None
    is_stale: bool = False
    stale_reason: str | None = None
    api_warning: str | None = None
    rate_limited: bool = False
    retry_after_seconds: int | None = None
    error_code: str | None = None
    us_aqi: float | None = None
    european_aqi: float | None = None
    aqi_category: str = "Unavailable"
    indian_aqi: IndianAQISummary = Field(default_factory=IndianAQISummary)
    pollutants: list[PollutantReading]
    hourly_trend: list[HourlyTrendPoint] = Field(default_factory=list)
    error_detail: str | None = None


class LocationSearchResponse(BaseModel):
    """Result wrapper for location presets and geocoding queries."""

    locations: list[LocationOption]
    data_status: DataStatus
    rate_limited: bool = False
    retry_after_seconds: int | None = None
    error_detail: str | None = None
