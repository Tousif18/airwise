"""Automated tests for Phase 3: Indoor Air Quality Advisor."""

from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings
from app.core.dependencies import get_air_quality_service, get_indoor_advisor_service
from app.main import app
from app.schemas.air_quality import (
    AirQualityOverviewResponse,
    DataStatus,
    IndianAQISummary,
    LocationOption,
    PollutantReading,
    ValueKind,
)
from app.schemas.assistant import PriorityLevel, ResponseSourceMode
from app.schemas.indoor import (
    GeminiIndoorGuidance,
    HomeEnvironmentProfile,
    HomeType,
    IndoorRecommendationCard,
    IndoorRecommendationCategory,
    KitchenVentilationType,
    WindowVentilationType,
)
from app.services.gemini_service import GeminiAssistantService
from app.services.indoor_advisor import IndoorAirAdvisorService


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


def _sample_outdoor_aq(available: bool = True) -> AirQualityOverviewResponse:
    if not available:
        return AirQualityOverviewResponse(
            location=_sample_location(),
            data_status=DataStatus.UNAVAILABLE,
            telemetry_kind=ValueKind.ESTIMATED,
            aqi_category="Unavailable",
            indian_aqi=IndianAQISummary(
                status=DataStatus.UNAVAILABLE,
                unavailable_reason="Open-Meteo unavailable.",
            ),
            pollutants=[],
            error_detail="Open-Meteo down",
        )
    return AirQualityOverviewResponse(
        location=_sample_location(),
        data_status=DataStatus.LIVE,
        telemetry_kind=ValueKind.ESTIMATED,
        observation_time="2026-11-26T22:00",
        us_aqi=172.0,
        european_aqi=76.0,
        aqi_category="Unhealthy",
        indian_aqi=IndianAQISummary(
            aqi=235,
            category="Poor",
            status=DataStatus.LIVE,
            prominent_pollutant="PM2.5",
            prominent_pollutant_key="pm2_5",
            valid_pollutant_count=3,
        ),
        pollutants=[
            PollutantReading(
                key="pm2_5",
                label="Fine Particulate Matter",
                formula="PM2.5",
                value=78.0,
                unit="μg/m³",
                status=DataStatus.LIVE,
                value_kind=ValueKind.ESTIMATED,
                guideline_24h=15.0,
                description="Fine particles",
            )
        ],
    )


def _sample_home() -> HomeEnvironmentProfile:
    return HomeEnvironmentProfile(
        home_type=HomeType.APARTMENT,
        room_count=3,
        kitchen_ventilation=KitchenVentilationType.WINDOW_ONLY,
        windows_ventilation=WindowVentilationType.SINGLE_SIDE_WINDOWS,
        has_air_purifier=True,
        has_children=True,
        has_older_adults=True,
        has_respiratory_sensitivity=True,
    )


def _valid_gemini_indoor_guidance() -> GeminiIndoorGuidance:
    categories = [
        (IndoorRecommendationCategory.PM25_REDUCTION, "Indoor PM2.5 Reduction", "Seal Exterior Door & Window Gaps"),
        (IndoorRecommendationCategory.SAFE_VENTILATION, "Safe Ventilation", "Keep Windows Closed During Peak Smog"),
        (IndoorRecommendationCategory.KITCHEN_SMOKE, "Kitchen Smoke", "Contain Cooking Smoke Without Chimney"),
        (IndoorRecommendationCategory.DUST_CLEANING, "Dust & Cleaning", "Damp-Mop Floors Instead of Dry Sweeping"),
        (IndoorRecommendationCategory.AIR_PURIFIER, "Air Purifier & Filters", "Place Purifier in Children's Bedroom"),
    ]
    cards = [
        IndoorRecommendationCard(
            category=cat,
            category_label=label,
            title=title,
            description="Practical protective step tailored to your apartment and outdoor air quality.",
            action_steps=["Follow step 1", "Follow step 2"],
            priority=PriorityLevel.HIGH if cat != IndoorRecommendationCategory.DUST_CLEANING else PriorityLevel.MEDIUM,
            reason="Outdoor US AQI is 172 and Indian CPCB AQI is 235 with children and older adults at home.",
            expected_benefit="Reduces indoor particulate exposure without inventing indoor sensor values.",
        )
        for cat, label, title in categories
    ]
    return GeminiIndoorGuidance(
        summary="Keep windows closed during elevated Kolkata smog and isolate kitchen fumes while running your bedroom HEPA purifier.",
        ventilation_verdict="Keep exterior windows closed now; ventilate briefly only during cleaner midday hours.",
        recommendations=cards,
        reasoning="Combined user-provided apartment details with Open-Meteo outdoor estimates.",
        limitations=["Indoor sensor readings are unavailable."],
    )


@pytest.mark.asyncio
async def test_indoor_advisor_fallback_covers_all_five_domains_and_never_fakes_sensors() -> None:
    settings = Settings(gemini_api_key="")
    gemini = GeminiAssistantService(settings)
    advisor = IndoorAirAdvisorService(settings=settings, gemini_service=gemini)

    res = await advisor.generate_recommendations(
        home=_sample_home(),
        air_quality=_sample_outdoor_aq(available=True),
    )

    assert res.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert res.is_ai_generated is False
    assert res.data_attribution.indoor_sensor_readings_available is False
    assert "not medical advice" in res.disclaimer.lower()
    returned_categories = {rec.category for rec in res.recommendations}
    assert returned_categories == {
        IndoorRecommendationCategory.PM25_REDUCTION,
        IndoorRecommendationCategory.SAFE_VENTILATION,
        IndoorRecommendationCategory.KITCHEN_SMOKE,
        IndoorRecommendationCategory.DUST_CLEANING,
        IndoorRecommendationCategory.AIR_PURIFIER,
    }


@pytest.mark.asyncio
async def test_indoor_advisor_missing_outdoor_data_handled_safely() -> None:
    settings = Settings(gemini_api_key="")
    gemini = GeminiAssistantService(settings)
    advisor = IndoorAirAdvisorService(settings=settings, gemini_service=gemini)

    res = await advisor.generate_recommendations(
        home=_sample_home(),
        air_quality=_sample_outdoor_aq(available=False),
    )

    assert res.outdoor_conditions.data_status == DataStatus.UNAVAILABLE
    assert res.data_attribution.indoor_sensor_readings_available is False
    assert "unavailable" in res.ventilation_verdict.lower()


@pytest.mark.asyncio
async def test_indoor_advisor_gemini_success_and_unsafe_rejection() -> None:
    valid_guidance = _valid_gemini_indoor_guidance()

    class WorkingModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=valid_guidance, text=valid_guidance.model_dump_json())

    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-3.8-flash")
    gemini = GeminiAssistantService(
        settings=settings,
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=WorkingModels())),
    )
    advisor = IndoorAirAdvisorService(settings=settings, gemini_service=gemini)

    ok_res = await advisor.generate_recommendations(
        home=_sample_home(),
        air_quality=_sample_outdoor_aq(available=True),
    )
    assert ok_res.response_source == ResponseSourceMode.GEMINI
    assert ok_res.is_ai_generated is True
    assert ok_res.model_used == "gemini-3.8-flash"
    assert ok_res.fallback_reason is None
    assert len(ok_res.recommendations) == 5

    # Unsafe indoor plant claim triggers deterministic fallback
    unsafe = valid_guidance.model_copy(
        update={"summary": "Use houseplants because plants remove indoor air pollution completely."}
    )

    class UnsafeModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=unsafe, text=unsafe.model_dump_json())

    gemini_unsafe = GeminiAssistantService(
        settings=settings,
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=UnsafeModels())),
    )
    advisor_unsafe = IndoorAirAdvisorService(settings=settings, gemini_service=gemini_unsafe)
    fb_res = await advisor_unsafe.generate_recommendations(
        home=_sample_home(),
        air_quality=_sample_outdoor_aq(available=True),
    )
    assert fb_res.response_source == ResponseSourceMode.RULE_BASED_FALLBACK
    assert fb_res.is_ai_generated is False
    assert "safety guardrail" in (fb_res.fallback_reason or "").lower()


def test_indoor_recommendations_endpoint_validation_and_response() -> None:
    class StubAQ:
        async def get_air_quality(self, location: LocationOption, force_refresh: bool = False):
            return _sample_outdoor_aq(available=True)

    valid_guidance = _valid_gemini_indoor_guidance()

    class WorkingModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=valid_guidance, text=valid_guidance.model_dump_json())

    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-3.8-flash")
    gemini = GeminiAssistantService(
        settings=settings,
        client_factory=lambda *_: SimpleNamespace(aio=SimpleNamespace(models=WorkingModels())),
    )
    advisor = IndoorAirAdvisorService(settings=settings, gemini_service=gemini)

    app.dependency_overrides[get_air_quality_service] = lambda: StubAQ()
    app.dependency_overrides[get_indoor_advisor_service] = lambda: advisor

    try:
        client = TestClient(app)

        bad_loc = client.post(
            "/api/v1/indoor/recommendations",
            json={"location_id": "non-existent-city"},
        )
        assert bad_loc.status_code == 404

        res = client.post(
            "/api/v1/indoor/recommendations",
            json={
                "location_id": "kolkata-in",
                "home_environment": _sample_home().model_dump(mode="json"),
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["response_source"] == "gemini"
        assert body["is_ai_generated"] is True
        assert body["data_attribution"]["indoor_sensor_readings_available"] is False
        assert len(body["recommendations"]) == 5
        assert "not medical advice" in body["disclaimer"].lower()
    finally:
        app.dependency_overrides.clear()



@pytest.mark.asyncio
async def test_cross_ventilation_advice_stays_cautious_when_outdoor_data_is_unavailable() -> None:
    settings = Settings(gemini_api_key="")
    advisor = IndoorAirAdvisorService(
        settings=settings,
        gemini_service=GeminiAssistantService(settings),
    )
    home = _sample_home().model_copy(
        update={"windows_ventilation": WindowVentilationType.CROSS_VENTILATION}
    )

    response = await advisor.generate_recommendations(
        home=home,
        air_quality=_sample_outdoor_aq(available=False),
    )

    ventilation = next(
        card
        for card in response.recommendations
        if card.category == IndoorRecommendationCategory.SAFE_VENTILATION
    )
    combined_advice = " ".join(
        [ventilation.title, ventilation.description, *ventilation.action_steps]
    ).lower()

    assert "unavailable" in response.ventilation_verdict.lower()
    assert "15–20 minutes" not in combined_advice
    assert "cleaner hours" not in combined_advice
    assert "brief cautious airing" in combined_advice
