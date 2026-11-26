"""Health and capability endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import get_gemini_placeholder_service
from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health and public integration capabilities."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        open_meteo_configured=bool(settings.open_meteo_air_quality_url),
        gemini_configured=settings.gemini_configured,
        gemini_model=settings.gemini_model,
        cache_ttl_seconds=settings.air_quality_cache_ttl_seconds,
    )


@router.get("/assistant/status")
async def assistant_status() -> dict[str, str | bool]:
    """Return Gemini AI Assistant readiness metadata."""
    return get_gemini_placeholder_service().get_status()
