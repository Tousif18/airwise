"""AirWise AI Assistant endpoints for chat, structured recommendations, and health."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.family import get_stored_family_profile
from app.core.dependencies import get_air_quality_service, get_gemini_service
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantHealthResponse,
    AssistantRecommendationsRequest,
    AssistantStructuredResponse,
)
from app.services.gemini_service import GeminiAssistantService
from app.services.locations import resolve_location_selection
from app.services.open_meteo import OpenMeteoAirQualityService

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/health", response_model=AssistantHealthResponse)
async def assistant_health(
    gemini_service: GeminiAssistantService = Depends(get_gemini_service),
) -> AssistantHealthResponse:
    """Return AI Assistant readiness and fallback capability without exposing secrets."""
    return gemini_service.get_health()


@router.get("/status", include_in_schema=False)
async def assistant_status(
    gemini_service: GeminiAssistantService = Depends(get_gemini_service),
) -> dict[str, str | bool]:
    """Backward-compatible status endpoint for AI Assistant readiness."""
    return gemini_service.get_status()


@router.post("/chat", response_model=AssistantStructuredResponse)
async def assistant_chat(
    payload: AssistantChatRequest,
    air_quality_service: OpenMeteoAirQualityService = Depends(get_air_quality_service),
    gemini_service: GeminiAssistantService = Depends(get_gemini_service),
) -> AssistantStructuredResponse:
    """Answer a family air-quality question grounded in Open-Meteo telemetry and safety rules."""
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
    profile = payload.family_profile or get_stored_family_profile()

    return await gemini_service.generate_guidance(
        air_quality=air_quality,
        profile=profile,
        question=payload.question,
        conversation_history=payload.conversation_history,
    )


@router.post("/recommendations", response_model=AssistantStructuredResponse)
async def assistant_recommendations(
    payload: AssistantRecommendationsRequest,
    air_quality_service: OpenMeteoAirQualityService = Depends(get_air_quality_service),
    gemini_service: GeminiAssistantService = Depends(get_gemini_service),
) -> AssistantStructuredResponse:
    """Generate structured household recommendations for the selected location and focus area."""
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
    profile = payload.family_profile or get_stored_family_profile()

    return await gemini_service.generate_guidance(
        air_quality=air_quality,
        profile=profile,
        question=None,
        focus_area=payload.focus_area,
    )
