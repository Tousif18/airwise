"""Indoor Air Quality Advisor endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_air_quality_service, get_indoor_advisor_service
from app.schemas.indoor import IndoorAdvisorRequest, IndoorAdvisorResponse
from app.schemas.errors import ErrorResponse, RateLimitErrorResponse
from app.services.indoor_advisor import IndoorAirAdvisorService
from app.services.locations import resolve_location_selection
from app.services.open_meteo import OpenMeteoAirQualityService

router = APIRouter(prefix="/indoor", tags=["indoor"])


@router.post(
    "/recommendations",
    response_model=IndoorAdvisorResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid Content-Length header."},
        404: {"model": ErrorResponse, "description": "Unknown preset location."},
        413: {"model": ErrorResponse, "description": "Request body exceeds 64 KB."},
        422: {"model": ErrorResponse, "description": "Request validation failed."},
        429: {"model": RateLimitErrorResponse, "description": "AI request rate limit exceeded."},
    },
)
async def get_indoor_recommendations(
    payload: IndoorAdvisorRequest,
    air_quality_service: OpenMeteoAirQualityService = Depends(get_air_quality_service),
    indoor_service: IndoorAirAdvisorService = Depends(get_indoor_advisor_service),
) -> IndoorAdvisorResponse:
    """Generate personalized indoor air-quality recommendations from home setup and outdoor telemetry."""
    location = resolve_location_selection(
        location_id=payload.location_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        name=payload.location_name,
        region=payload.region,
        country=payload.country,
        timezone=payload.timezone,
    )
    if location is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown preset location_id '{payload.location_id}'. "
                "Provide latitude and longitude for custom locations."
            ),
        )

    air_quality = await air_quality_service.get_air_quality(
        location=location,
        force_refresh=payload.force_refresh,
    )
    return await indoor_service.generate_recommendations(
        home=payload.home_environment,
        air_quality=air_quality,
    )
