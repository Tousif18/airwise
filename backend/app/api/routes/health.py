"""Health and capability endpoints."""

from fastapi import APIRouter, Request

from app.api.query_validation import reject_unknown_query_parameters

from app.core.config import get_settings
from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Return service health and public integration capabilities."""
    reject_unknown_query_parameters(request)
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
