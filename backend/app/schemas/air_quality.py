"""Pydantic schemas for air quality, locations, and data freshness state."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class DataStatus(str, Enum):
    """Explicit indicator distinguishing live, cached, and unavailable readings."""

    LIVE = "live"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"


class LocationOption(BaseModel):
    """Geographic location metadata used for Open-Meteo queries."""

    id: str
    name: str
    region: str = ""
    country: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str = "auto"


class PollutantReading(BaseModel):
    """Single pollutant measurement with guideline context and freshness status."""

    key: str
    label: str
    formula: str
    value: float | None = None
    unit: str
    status: DataStatus
    guideline_24h: float | None = None
    description: str


class HourlyTrendPoint(BaseModel):
    """Hourly air quality trend point returned by Open-Meteo."""

    time: str
    us_aqi: float | None = None
    pm2_5: float | None = None
    pm10: float | None = None


class AirQualityOverviewResponse(BaseModel):
    """Full air quality payload for a selected location."""

    location: LocationOption
    data_status: DataStatus
    source: str = "Open-Meteo Air Quality API"
    fetched_at: datetime | None = None
    cached_at: datetime | None = None
    cache_expires_at: datetime | None = None
    us_aqi: float | None = None
    european_aqi: float | None = None
    aqi_category: str = "Unavailable"
    pollutants: list[PollutantReading]
    hourly_trend: list[HourlyTrendPoint] = Field(default_factory=list)
    error_detail: str | None = None


class LocationSearchResponse(BaseModel):
    """Result wrapper for location presets and geocoding queries."""

    locations: list[LocationOption]
    data_status: DataStatus
    error_detail: str | None = None
