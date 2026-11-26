"""Shared application dependencies and singleton service instances."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.decision_engine import DeterministicDecisionEngine
from app.services.gemini_service import GeminiAssistantService
from app.services.indoor_advisor import IndoorAirAdvisorService
from app.services.open_meteo import OpenMeteoAirQualityService


@lru_cache(maxsize=1)
def get_air_quality_service() -> OpenMeteoAirQualityService:
    """Provide singleton Open-Meteo service sharing the TTL cache."""
    return OpenMeteoAirQualityService(settings=get_settings())


@lru_cache(maxsize=1)
def get_decision_engine() -> DeterministicDecisionEngine:
    """Provide singleton deterministic air-quality decision engine."""
    return DeterministicDecisionEngine(settings=get_settings())


@lru_cache(maxsize=1)
def get_gemini_service() -> GeminiAssistantService:
    """Provide singleton Gemini AI Assistant service."""
    return GeminiAssistantService(
        settings=get_settings(),
        decision_engine=get_decision_engine(),
    )


@lru_cache(maxsize=1)
def get_indoor_advisor_service() -> IndoorAirAdvisorService:
    """Provide singleton Indoor Air Quality Advisor service."""
    return IndoorAirAdvisorService(
        settings=get_settings(),
        gemini_service=get_gemini_service(),
        decision_engine=get_decision_engine(),
    )


def get_gemini_placeholder_service() -> GeminiAssistantService:
    """Backward-compatible alias returning the Gemini AI Assistant service."""
    return get_gemini_service()
