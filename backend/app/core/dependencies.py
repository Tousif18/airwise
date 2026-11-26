"""Shared application dependencies and singleton service instances."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.gemini_service import GeminiAssistantPlaceholder
from app.services.open_meteo import OpenMeteoAirQualityService


@lru_cache(maxsize=1)
def get_air_quality_service() -> OpenMeteoAirQualityService:
    """Provide singleton Open-Meteo service sharing the TTL cache."""
    return OpenMeteoAirQualityService(settings=get_settings())


@lru_cache(maxsize=1)
def get_gemini_placeholder_service() -> GeminiAssistantPlaceholder:
    """Provide singleton Gemini status placeholder service."""
    return GeminiAssistantPlaceholder(settings=get_settings())
