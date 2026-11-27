"""Pydantic schemas for the AirWise AI Assistant, context builder, and structured output."""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.air_quality import DataStatus, ValueKind
from app.schemas.family import FamilyProfile
from app.schemas.location_validation import validate_timezone


class PriorityLevel(str, Enum):
    """Action urgency priority for recommendation cards."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, Enum):
    """Normalized deterministic air-quality risk posture."""

    UNKNOWN = "unknown"
    LOW = "low"
    MODERATE = "moderate"
    SENSITIVE_CAUTION = "sensitive_caution"
    HIGH = "high"
    VERY_HIGH = "very_high"
    HAZARDOUS = "hazardous"


class ResponseSourceMode(str, Enum):
    """Explicit indicator distinguishing Gemini AI output vs deterministic fallback."""

    GEMINI = "gemini"
    RULE_BASED_FALLBACK = "rule_based_fallback"


class AQIScaleReading(BaseModel):
    """Single AQI standard reading kept strictly separate from other AQI scales."""

    standard_name: str
    value: float | int | None = None
    category: str = "Unavailable"
    status: DataStatus
    value_kind: ValueKind | None = None
    prominent_pollutant: str | None = None
    unavailable_reason: str | None = None


class PollutantSnapshot(BaseModel):
    """Compact pollutant reading used inside assistant current_conditions."""

    key: str
    formula: str
    value: float | None = None
    unit: str
    guideline_24h: float | None = None
    status: DataStatus
    value_kind: ValueKind = ValueKind.ESTIMATED
    cpcb_sub_index: int | None = None
    cpcb_category: str | None = None


class CurrentConditionsSummary(BaseModel):
    """Structured snapshot of current air-quality conditions and telemetry integrity."""

    location_name: str
    region: str = ""
    country: str = ""
    data_status: DataStatus
    telemetry_kind: ValueKind = ValueKind.ESTIMATED
    is_stale: bool = False
    stale_reason: str | None = None
    risk_level: RiskLevel
    us_aqi: AQIScaleReading
    european_aqi: AQIScaleReading
    indian_cpcb_aqi: AQIScaleReading
    key_pollutants: list[PollutantSnapshot] = Field(default_factory=list)
    source: str


class RecommendationItem(BaseModel):
    """Individual structured recommendation card."""

    title: str = Field(..., min_length=3, max_length=140)
    description: str = Field(..., min_length=5, max_length=500)
    priority: PriorityLevel
    reason: str = Field(..., min_length=5, max_length=400)
    expected_benefit: str = Field(..., min_length=5, max_length=300)


class GeminiGeneratedGuidance(BaseModel):
    """Validated JSON payload expected from Gemini Structured Outputs."""

    summary: str = Field(..., min_length=10, max_length=800)
    recommendations: list[RecommendationItem] = Field(..., min_length=1, max_length=6)
    indoor_actions: list[str] = Field(..., min_length=1, max_length=6)
    outdoor_actions: list[str] = Field(..., min_length=1, max_length=6)
    sustainable_alternatives: list[str] = Field(..., min_length=1, max_length=6)
    reasoning: str = Field(..., min_length=10, max_length=1200)
    estimated_environmental_impact: str = Field(..., min_length=5, max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class AssistantStructuredResponse(BaseModel):
    """Full structured API response returned by /chat and /recommendations."""

    summary: str
    current_conditions: CurrentConditionsSummary
    recommendations: list[RecommendationItem]
    indoor_actions: list[str]
    outdoor_actions: list[str]
    sustainable_alternatives: list[str]
    reasoning: str
    estimated_environmental_impact: str
    limitations: list[str]
    data_timestamp: str
    response_source: ResponseSourceMode
    is_ai_generated: bool
    model_used: str | None = None
    fallback_reason: str | None = None
    disclaimer: str = (
        "Informational urban air-quality guidance only — not medical diagnosis or treatment."
    )


class ChatTurn(BaseModel):
    """Single historical conversation message for multi-turn context."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1500)

    @field_validator("content")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation turn content cannot be blank.")
        return cleaned


class AssistantLocationMixin(BaseModel):
    """Shared validated location parameters for assistant requests."""

    location_id: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = Field(default=None, max_length=120)
    region: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=120)
    timezone: str = Field(default="auto", max_length=64)
    family_profile: FamilyProfile | None = None
    force_refresh: bool = False

    @field_validator("timezone")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        return validate_timezone(value)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> "AssistantLocationMixin":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        return self


class AssistantChatRequest(AssistantLocationMixin):
    """Request body for POST /api/v1/assistant/chat."""

    question: str = Field(..., min_length=1, max_length=1000)
    conversation_history: list[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty or whitespace only.")
        return cleaned


class AssistantRecommendationsRequest(AssistantLocationMixin):
    """Request body for POST /api/v1/assistant/recommendations."""

    focus_area: Literal[
        "daily_plan", "indoor", "outdoor", "commute", "sustainability"
    ] = "daily_plan"


class AssistantHealthResponse(BaseModel):
    """Public AI assistant capability and health metadata."""

    status: str
    gemini_configured: bool
    gemini_available: bool
    gemini_model: str
    fallback_mode_available: bool = True
    message: str
