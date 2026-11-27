"""Health and capability endpoints."""

from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.query_validation import reject_unknown_query_parameters
from app.core.config import get_settings
from app.schemas.errors import ErrorResponse
from app.schemas.system import HealthResponse, ReadinessResponse

router = APIRouter(tags=["system"])


def _is_http_url_configured(value: str) -> bool:
    """Return whether a configured upstream URL is an absolute HTTP(S) URL."""
    try:
        parsed = urlsplit(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


@router.get("/health/live")
async def liveness_check(request: Request) -> dict[str, str]:
    """Confirm that the API process is running and able to respond."""
    reject_unknown_query_parameters(request)
    return {"status": "ok"}


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Required local configuration is invalid."}},
)
async def readiness_check(request: Request) -> ReadinessResponse | JSONResponse:
    """Check required local configuration without depending on upstream availability."""
    reject_unknown_query_parameters(request)
    settings = get_settings()
    checks = {
        "open_meteo_air_quality_url": _is_http_url_configured(
            settings.open_meteo_air_quality_url
        ),
        "open_meteo_geocoding_url": _is_http_url_configured(
            settings.open_meteo_geocoding_url
        ),
    }
    is_ready = all(checks.values())
    response = ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        app_name=settings.app_name,
        environment=settings.app_env,
        checks=checks,
    )
    if not is_ready:
        return JSONResponse(status_code=503, content=response.model_dump())
    return response


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={422: {"model": ErrorResponse, "description": "Invalid query parameters."}},
)
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
