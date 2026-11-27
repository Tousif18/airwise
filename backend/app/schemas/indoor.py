"""Pydantic schemas for Phase 3: Indoor Air Quality Advisor."""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.air_quality import DataStatus, ValueKind
from app.schemas.location_validation import validate_timezone
from app.schemas.assistant import (
    CurrentConditionsSummary,
    PriorityLevel,
    ResponseSourceMode,
)


class HomeType(str, Enum):
    """Residential building type."""

    APARTMENT = "apartment"
    INDEPENDENT_HOUSE = "independent_house"


class KitchenVentilationType(str, Enum):
    """Available kitchen exhaust or ventilation setup."""

    CHIMNEY_EXHAUST = "chimney_exhaust"
    EXHAUST_FAN = "exhaust_fan"
    WINDOW_ONLY = "window_only"
    NONE = "none"


class WindowVentilationType(str, Enum):
    """Natural window ventilation layout in the home."""

    CROSS_VENTILATION = "cross_ventilation"
    SINGLE_SIDE_WINDOWS = "single_side_windows"
    LIMITED_OR_SEALED = "limited_or_sealed"


class IndoorRecommendationCategory(str, Enum):
    """Five core indoor air protection domains."""

    PM25_REDUCTION = "pm25_reduction"
    SAFE_VENTILATION = "safe_ventilation"
    KITCHEN_SMOKE = "kitchen_smoke"
    DUST_CLEANING = "dust_cleaning"
    AIR_PURIFIER = "air_purifier"


class HomeEnvironmentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    """User-provided home environment details (distinct from sensor readings)."""

    home_type: HomeType = HomeType.APARTMENT
    room_count: int = Field(default=3, ge=1, le=20)
    kitchen_ventilation: KitchenVentilationType = KitchenVentilationType.EXHAUST_FAN
    windows_ventilation: WindowVentilationType = WindowVentilationType.CROSS_VENTILATION
    has_air_purifier: bool = False
    has_children: bool = False
    has_older_adults: bool = False
    has_respiratory_sensitivity: bool = False
    notes: str = Field(default="", max_length=240)


class IndoorRecommendationCard(BaseModel):
    """Single actionable indoor air recommendation card with priority and category."""

    category: IndoorRecommendationCategory
    category_label: str = Field(..., min_length=3, max_length=80)
    title: str = Field(..., min_length=3, max_length=140)
    description: str = Field(..., min_length=10, max_length=550)
    action_steps: list[str] = Field(..., min_length=1, max_length=5)
    priority: PriorityLevel
    reason: str = Field(..., min_length=5, max_length=400)
    expected_benefit: str = Field(..., min_length=5, max_length=300)


class GeminiIndoorGuidance(BaseModel):
    """Structured JSON output expected from Gemini for Indoor Air Guide."""

    summary: str = Field(..., min_length=10, max_length=700)
    ventilation_verdict: str = Field(..., min_length=5, max_length=300)
    recommendations: list[IndoorRecommendationCard] = Field(..., min_length=5, max_length=6)
    reasoning: str = Field(..., min_length=10, max_length=1000)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class IndoorDataAttribution(BaseModel):
    """Explicit separation between user-provided home context and outdoor telemetry."""

    indoor_sensor_readings_available: bool = False
    indoor_sensor_note: str = (
        "No indoor PM2.5 or gas sensor readings are connected; indoor guidance is "
        "inferred from your user-provided home setup and outdoor Open-Meteo telemetry."
    )
    user_provided_home_profile: HomeEnvironmentProfile
    outdoor_data_status: DataStatus
    outdoor_telemetry_kind: ValueKind


class IndoorAdvisorRequest(BaseModel):
    """Request body for POST /api/v1/indoor/recommendations."""

    home_environment: HomeEnvironmentProfile = Field(default_factory=HomeEnvironmentProfile)
    location_id: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = Field(default=None, max_length=120)
    region: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=120)
    timezone: str = Field(default="auto", max_length=64)
    force_refresh: bool = False

    @field_validator("timezone")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        return validate_timezone(value)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> "IndoorAdvisorRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        return self


class IndoorAdvisorResponse(BaseModel):
    """Full structured response returned by POST /api/v1/indoor/recommendations."""

    summary: str
    ventilation_verdict: str
    outdoor_conditions: CurrentConditionsSummary
    data_attribution: IndoorDataAttribution
    recommendations: list[IndoorRecommendationCard]
    reasoning: str
    limitations: list[str]
    data_timestamp: str
    response_source: ResponseSourceMode
    is_ai_generated: bool
    model_used: str | None = None
    fallback_reason: str | None = None
    disclaimer: str = (
        "Informational indoor air-quality guidance only — not medical advice, diagnosis, or treatment."
    )
