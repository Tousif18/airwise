"""Automated tests for AirWise Phase 2: Family Profile, Decision Engine, Context Builder, Gemini Service, and Assistant API."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.core.dependencies import get_air_quality_service, get_gemini_service
from app.main import app
from app.schemas.air_quality import (
    AirQualityOverviewResponse,
    DataStatus,
    HourlyTrendPoint,
    IndianAQISummary,
    LocationOption,
    PollutantReading,
    ValueKind,
)
from app.schemas.assistant import (
    GeminiGeneratedGuidance,
    PriorityLevel,
    RecommendationItem,
    ResponseSourceMode,
    RiskLevel,
)
from app.schemas.family import CommuteMethod, FamilyProfile, SensitivityLevel, VentilationPreference
from app.services.context_builder import build_ai_context
from app.services.decision_engine import DeterministicDecisionEngine
from app.services.gemini_service import GeminiAssistantService


def _sample_location() -> LocationOption:
    return LocationOption(
        id="kolkata-in",
        name="Kolkata",
        region="West Bengal",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
        timezone="Asia/Kolkata",
    )


def _sample_profile(**overrides) -> FamilyProfile:
    base = {
        "city": "Kolkata",
        "location_id": "kolkata-in",
        "location_label": "Kolkata, West Bengal, India",
        "household_size": 4,
        "children_count": 1,
        "elderly_count": 1,
        "has_respiratory_condition": True,
        "respiratory_vulnerability": "Mild smog cough sensitivity",
        "sensitivity_level": SensitivityLevel.HIGH,
        "commute_method": CommuteMethod.TWO_WHEELER,
        "outdoor_activity_schedule": "Morning school commute 8 AM and evening park 5 PM",
        "ventilation_preference": VentilationPreference.LOW_SMOG_WINDOWS,
        "has_air_purifier": True,
    }
    base.update(overrides)
    return FamilyProfile(**base)


def _sample_air_quality(
    *,
    us_aqi: float | None = 165.0,
    european_aqi: float | None = 72.0,
    cpcb_aqi: int | None = 220,
    cpcb_category: str = "Poor",
    pm25: float | None = 85.0,
    no2: float | None = 48.0,
    data_status: DataStatus = DataStatus.LIVE,
    is_stale: bool = False,
    stale_reason: str | None = None,
    observation_time: str | None = "2026-11-26T18:00",
    fetched_at: datetime | None = None,
) -> AirQualityOverviewResponse:
    if data_status == DataStatus.UNAVAILABLE:
        return AirQualityOverviewResponse(
            location=_sample_location(),
            data_status=DataStatus.UNAVAILABLE,
            telemetry_kind=ValueKind.ESTIMATED,
            observation_time=None,
            fetched_at=None,
            us_aqi=None,
            european_aqi=None,
            aqi_category="Unavailable",
            indian_aqi=IndianAQISummary(
                status=DataStatus.UNAVAILABLE,
                unavailable_reason="Open-Meteo telemetry unavailable.",
            ),
            pollutants=[
                PollutantReading(
                    key="pm2_5",
                    label="Fine Particulate Matter",
                    formula="PM2.5",
                    value=None,
                    unit="μg/m³",
                    status=DataStatus.UNAVAILABLE,
                    value_kind=ValueKind.ESTIMATED,
                    guideline_24h=15.0,
                    description="Fine particles",
                )
            ],
            hourly_trend=[],
            error_detail="Upstream Open-Meteo timeout",
        )

    return AirQualityOverviewResponse(
        location=_sample_location(),
        data_status=data_status,
        telemetry_kind=ValueKind.ESTIMATED,
        observation_time=observation_time,
        fetched_at=fetched_at or datetime.now(timezone.utc),
        is_stale=is_stale,
        stale_reason=stale_reason,
        us_aqi=us_aqi,
        european_aqi=european_aqi,
        aqi_category="Unhealthy" if (us_aqi or 0) > 150 else "Moderate",
        indian_aqi=IndianAQISummary(
            aqi=cpcb_aqi,
            category=cpcb_category if cpcb_aqi is not None else "Unavailable",
            status=data_status if cpcb_aqi is not None else DataStatus.UNAVAILABLE,
            prominent_pollutant="PM2.5" if cpcb_aqi is not None else None,
            prominent_pollutant_key="pm2_5" if cpcb_aqi is not None else None,
            valid_pollutant_count=3 if cpcb_aqi is not None else 1,
            unavailable_reason=(
                None
                if cpcb_aqi is not None
                else "Indian CPCB AQI unavailable: minimum 3 pollutants required."
            ),
        ),
        pollutants=[
            PollutantReading(
                key="pm2_5",
                label="Fine Particulate Matter",
                formula="PM2.5",
                value=pm25,
                unit="μg/m³",
                status=data_status if pm25 is not None else DataStatus.UNAVAILABLE,
                value_kind=ValueKind.ESTIMATED,
                guideline_24h=15.0,
                description="Fine particles",
            ),
            PollutantReading(
                key="nitrogen_dioxide",
                label="Nitrogen Dioxide",
                formula="NO₂",
                value=no2,
                unit="μg/m³",
                status=data_status if no2 is not None else DataStatus.UNAVAILABLE,
                value_kind=ValueKind.ESTIMATED,
                guideline_24h=25.0,
                description="Traffic gas",
            ),
        ],
        hourly_trend=[
            HourlyTrendPoint(
                time="2026-11-26T22:00",
                us_aqi=120.0,
                pm2_5=52.0,
                pm10=95.0,
                value_kind=ValueKind.FORECAST,
            )
        ],
    )


def _valid_gemini_guidance() -> GeminiGeneratedGuidance:
    return GeminiGeneratedGuidance(
        summary="Keep outdoor play brief for your child today because PM2.5 and US AQI are elevated.",
        recommendations=[
            RecommendationItem(
                title="Shift Outdoor Play Indoors Today",
                description="Avoid vigorous playground exertion during high particulate hours.",
                priority=PriorityLevel.HIGH,
                reason="US AQI is 165 (Unhealthy) and Indian CPCB AQI is 220 (Poor) with a child and respiratory sensitivity in the household.",
                expected_benefit="Reduces fine-particle inhalation during peak winter smog.",
            )
        ],
        indoor_actions=[
            "Keep windows closed during smog peaks and run your air purifier (reduces particulates, though does not eliminate all exposure)."
        ],
        outdoor_actions=[
            "Wear a well-fitted N95 mask for unavoidable two-wheeler trips."
        ],
        sustainable_alternatives=[
            "Switch from a two-wheeler to enclosed metro or bus transit when feasible."
        ],
        reasoning="Evaluated US AQI (165), European AQI (72), and Indian CPCB AQI (220) separately alongside high household sensitivity.",
        estimated_environmental_impact="Shifting two daily commutes to metro/bus avoids local tailpipe NO2 and PM2.5.",
        limitations=["Open-Meteo readings are CAMS model estimates rather than street-level ground sensors."],
    )


# ---------------------------------------------------------------------------
# 1. Family Profile Validation & Endpoints
# ---------------------------------------------------------------------------


def test_family_profile_validation_rejects_excess_dependents() -> None:
    with pytest.raises(ValueError, match="children_count \\+ elderly_count"):
        _sample_profile(household_size=2, children_count=2, elderly_count=1)


def test_family_profile_is_not_exposed_by_shared_backend_endpoints() -> None:
    client = TestClient(app)
    for path in ("/api/v1/family/profile", "/api/v1/family-profile"):
        assert client.get(path).status_code == 404
        assert client.put(path, json=_sample_profile().model_dump(mode="json")).status_code == 404


# ---------------------------------------------------------------------------
# 2. Decision Engine & Context Builder (Missing, Stale, Scale Separation)
# ---------------------------------------------------------------------------


def test_decision_engine_separates_scales_and_never_invents_cpcb() -> None:
    engine = DeterministicDecisionEngine(Settings())
    aq = _sample_air_quality(us_aqi=145.0, european_aqi=55.0, cpcb_aqi=None, pm25=54.0)
    profile = _sample_profile(sensitivity_level=SensitivityLevel.MODERATE, has_respiratory_condition=False)

    assessment = engine.assess(aq, profile)

    assert assessment.current_conditions.us_aqi.value == 145.0
    assert assessment.current_conditions.european_aqi.value == 55.0
    assert assessment.current_conditions.indian_cpcb_aqi.value is None
    assert assessment.current_conditions.indian_cpcb_aqi.status == DataStatus.UNAVAILABLE
    assert "Indian CPCB AQI (NAQI)" in assessment.missing_data_items
    assert any("minimum 3 pollutants" in lim for lim in assessment.limitations)
    assert assessment.risk_level in (RiskLevel.SENSITIVE_CAUTION, RiskLevel.HIGH)


def test_decision_engine_escalates_for_sensitive_household() -> None:
    engine = DeterministicDecisionEngine(Settings())
    aq = _sample_air_quality(us_aqi=85.0, european_aqi=35.0, cpcb_aqi=90, cpcb_category="Satisfactory", pm25=28.0)
    sensitive_profile = _sample_profile(children_count=1, sensitivity_level=SensitivityLevel.HIGH)

    assessment = engine.assess(aq, sensitive_profile)
    assert assessment.is_sensitive_household is True
    assert assessment.risk_level == RiskLevel.SENSITIVE_CAUTION
    assert assessment.outdoor_play_posture == "limit_intense"


def test_missing_aqi_data_in_context_and_fallback() -> None:
    engine = DeterministicDecisionEngine(Settings())
    aq = _sample_air_quality(data_status=DataStatus.UNAVAILABLE)
    profile = _sample_profile()

    assessment = engine.assess(aq, profile)
    context = build_ai_context(aq, profile, assessment, question="Is it safe to play outside?")

    assert assessment.air_quality_available is False
    assert assessment.risk_level == RiskLevel.UNKNOWN
    assert context["telemetry_integrity"]["air_quality_available"] is False
    assert context["data_classification"]["observed_ground_sensor_data"]["available"] is False
    assert "MUST NOT invent" in context["data_classification"]["missing_data"]["instruction"]

    fallback = engine.build_fallback_response(assessment, aq, profile, question="Is it safe to play outside?")
    assert fallback.is_ai_generated is False
    assert fallback.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert "unavailable" in fallback.summary.lower()


def test_stale_environmental_data_is_detected_and_flagged() -> None:
    engine = DeterministicDecisionEngine(Settings(air_quality_observation_stale_minutes=60))
    old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    aq = _sample_air_quality(
        data_status=DataStatus.CACHED,
        is_stale=True,
        stale_reason="Cached telemetry is 25 min old.",
        observation_time=old_time,
    )
    profile = _sample_profile()
    assessment = engine.assess(aq, profile)
    context = build_ai_context(aq, profile, assessment, question="Should we ventilate?")

    assert assessment.is_stale is True
    assert assessment.current_conditions.is_stale is True
    assert any("Stale environmental data" in lim for lim in assessment.limitations)
    assert context["telemetry_integrity"]["is_stale"] is True


# ---------------------------------------------------------------------------
# 3. Gemini Integration, Mocking, Invalid Responses & Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_unavailable_when_api_key_missing_returns_rule_based_fallback() -> None:
    service = GeminiAssistantService(Settings(gemini_api_key=""))
    aq = _sample_air_quality()
    profile = _sample_profile()

    result = await service.generate_guidance(
        air_quality=aq,
        profile=profile,
        question="Is it a good day for my child to play outdoors?",
    )

    assert result.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert result.is_ai_generated is False
    assert result.model_used is None
    assert "not configured" in (result.fallback_reason or "").lower()
    assert len(result.recommendations) >= 1
    assert result.current_conditions.us_aqi.value == 165.0


@pytest.mark.asyncio
async def test_gemini_exception_falls_back_gracefully() -> None:
    class FailingModels:
        async def generate_content(self, **kwargs):
            raise RuntimeError("Simulated Gemini outage")

    def failing_factory(api_key: str, timeout: float):
        return SimpleNamespace(aio=SimpleNamespace(models=FailingModels()))

    service = GeminiAssistantService(
        Settings(gemini_api_key="test-key-not-real", gemini_model="gemini-2.5-flash"),
        client_factory=failing_factory,
    )
    result = await service.generate_guidance(
        air_quality=_sample_air_quality(),
        profile=_sample_profile(),
        question="Should we ventilate our home right now?",
    )

    assert result.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert result.is_ai_generated is False
    assert result.fallback_reason == (
        "The AI assistant is temporarily unavailable; deterministic rule-based guidance was provided."
    )
    assert "Simulated Gemini outage" not in (result.fallback_reason or "")
    assert "RuntimeError" not in (result.fallback_reason or "")


@pytest.mark.asyncio
async def test_gemini_invalid_json_or_unsafe_claim_triggers_fallback() -> None:
    # 1. Invalid JSON string
    class MalformedModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=None, text="{not valid json")

    service_bad_json = GeminiAssistantService(
        Settings(gemini_api_key="test-key", gemini_model="gemini-2.5-flash"),
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=MalformedModels())),
    )
    res_bad_json = await service_bad_json.generate_guidance(
        air_quality=_sample_air_quality(),
        profile=_sample_profile(),
        question="How can we improve indoor air quality?",
    )
    assert res_bad_json.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert res_bad_json.is_ai_generated is False

    # 2. Unsafe claim (plants purify indoor pollution / 100% protection)
    unsafe_guidance = _valid_gemini_guidance().model_copy(
        update={
            "indoor_actions": [
                "Place houseplants everywhere because plants remove indoor air pollution and offer 100% protection."
            ]
        }
    )

    class UnsafeModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=unsafe_guidance, text=unsafe_guidance.model_dump_json())

    service_unsafe = GeminiAssistantService(
        Settings(gemini_api_key="test-key", gemini_model="gemini-2.5-flash"),
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=UnsafeModels())),
    )
    res_unsafe = await service_unsafe.generate_guidance(
        air_quality=_sample_air_quality(),
        profile=_sample_profile(),
        question="How can we improve indoor air quality?",
    )
    assert res_unsafe.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert res_unsafe.is_ai_generated is False
    assert "safety guardrail" in (res_unsafe.fallback_reason or "").lower()


@pytest.mark.asyncio
async def test_gemini_valid_structured_response_succeeds_with_mock() -> None:
    valid_guidance = _valid_gemini_guidance()

    class WorkingModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=valid_guidance, text=valid_guidance.model_dump_json())

    service = GeminiAssistantService(
        Settings(gemini_api_key="test-key", gemini_model="gemini-3.8-flash"),
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=WorkingModels())),
    )
    result = await service.generate_guidance(
        air_quality=_sample_air_quality(),
        profile=_sample_profile(),
        question="Is it a good day for my child to play outdoors?",
    )

    assert result.response_source == ResponseSourceMode.GEMINI
    assert result.is_ai_generated is True
    assert result.model_used == "gemini-3.8-flash"
    assert result.fallback_reason is None
    assert result.recommendations[0].priority == PriorityLevel.HIGH
    assert result.current_conditions.indian_cpcb_aqi.value == 220


@pytest.mark.asyncio
async def test_gemini_transient_server_error_rolls_over_to_fallback_model() -> None:
    from google.genai import errors as genai_errors

    valid_guidance = _valid_gemini_guidance()
    seen_models: list[str] = []

    class RolloverModels:
        async def generate_content(self, **kwargs):
            model_name = kwargs["model"]
            seen_models.append(model_name)
            if model_name == "gemini-3.8-flash":
                raise genai_errors.ServerError(
                    503,
                    {"error": {"code": 503, "status": "UNAVAILABLE", "message": "High demand"}},
                    None,
                )
            return SimpleNamespace(parsed=valid_guidance, text=valid_guidance.model_dump_json())

    service = GeminiAssistantService(
        Settings(
            gemini_api_key="test-key",
            gemini_model="gemini-3.8-flash",
            gemini_fallback_models_raw="gemini-3.5-flash-lite",
        ),
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=RolloverModels())),
    )
    result = await service.generate_guidance(
        air_quality=_sample_air_quality(),
        profile=_sample_profile(),
        question="Is it a good day for my child to play outdoors?",
    )

    assert seen_models == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert result.response_source == ResponseSourceMode.GEMINI
    assert result.is_ai_generated is True
    assert result.model_used == "gemini-3.5-flash-lite"
    assert result.fallback_reason is None


# ---------------------------------------------------------------------------
# 4. FastAPI Assistant Endpoints & Input Validation
# ---------------------------------------------------------------------------


def test_assistant_endpoints_validation_and_structured_output() -> None:
    class StubAirQualityService:
        async def get_air_quality(self, location: LocationOption, force_refresh: bool = False):
            return _sample_air_quality()

    valid_guidance = _valid_gemini_guidance()

    class WorkingModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=valid_guidance, text=valid_guidance.model_dump_json())

    stub_gemini = GeminiAssistantService(
        Settings(gemini_api_key="mock-secret-key", gemini_model="gemini-2.5-flash"),
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=WorkingModels())),
    )

    app.dependency_overrides[get_air_quality_service] = lambda: StubAirQualityService()
    app.dependency_overrides[get_gemini_service] = lambda: stub_gemini

    try:
        client = TestClient(app)

        # Health endpoint never leaks key
        health_res = client.get("/api/v1/assistant/health")
        assert health_res.status_code == 200
        health_body = health_res.json()
        assert health_body["status"] == "ok"
        assert health_body["gemini_configured"] is True
        assert health_body["fallback_mode_available"] is True
        assert "mock-secret-key" not in str(health_body)

        # Blank question rejected (422)
        blank_res = client.post("/api/v1/assistant/chat", json={"question": "   "})
        assert blank_res.status_code == 422

        # Half-specified coordinate pair rejected (422)
        half_coord_res = client.post(
            "/api/v1/assistant/chat",
            json={"question": "Check air quality", "latitude": 22.5},
        )
        assert half_coord_res.status_code == 422

        # Unknown preset rejected (404)
        unknown_loc_res = client.post(
            "/api/v1/assistant/chat",
            json={"question": "Check air quality", "location_id": "unknown-city-xx"},
        )
        assert unknown_loc_res.status_code == 404

        # Valid /chat request
        chat_res = client.post(
            "/api/v1/assistant/chat",
            json={
                "question": "Is it a good day for my child to play outdoors?",
                "location_id": "kolkata-in",
            },
        )
        assert chat_res.status_code == 200
        chat_body = chat_res.json()
        for required_field in (
            "summary",
            "current_conditions",
            "recommendations",
            "indoor_actions",
            "outdoor_actions",
            "sustainable_alternatives",
            "reasoning",
            "estimated_environmental_impact",
            "limitations",
            "data_timestamp",
        ):
            assert required_field in chat_body

        rec = chat_body["recommendations"][0]
        for rec_field in ("title", "description", "priority", "reason", "expected_benefit"):
            assert rec_field in rec

        # Valid /recommendations request
        rec_res = client.post(
            "/api/v1/assistant/recommendations",
            json={"focus_area": "daily_plan", "location_id": "kolkata-in"},
        )
        assert rec_res.status_code == 200
        assert rec_res.json()["is_ai_generated"] is True
    finally:
        app.dependency_overrides.clear()
