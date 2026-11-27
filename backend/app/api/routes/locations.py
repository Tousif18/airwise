"""Location presets and cached geocoding search endpoints."""

from fastapi import APIRouter, Depends, Query, Request

from app.api.query_validation import reject_unknown_query_parameters

from app.core.dependencies import get_location_search_service
from app.schemas.air_quality import DataStatus, LocationSearchResponse
from app.schemas.errors import ErrorResponse, RateLimitErrorResponse
from app.services.locations import LocationSearchService, get_preset_locations

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get(
    "/presets",
    response_model=LocationSearchResponse,
    responses={422: {"model": ErrorResponse, "description": "Invalid query parameters."}},
)
async def list_preset_locations(request: Request) -> LocationSearchResponse:
    """Return curated urban locations for instant dashboard monitoring."""
    reject_unknown_query_parameters(request)
    return LocationSearchResponse(
        locations=get_preset_locations(),
        data_status=DataStatus.LIVE,
    )


@router.get(
    "/search",
    response_model=LocationSearchResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid query parameters."},
        429: {"model": RateLimitErrorResponse, "description": "Location search rate limit exceeded."},
    },
)
async def search_city_locations(
    request: Request,
    q: str = Query(..., min_length=1, max_length=80, description="City or neighborhood name"),
    location_service: LocationSearchService = Depends(get_location_search_service),
) -> LocationSearchResponse:
    """Search matching cities via cached Open-Meteo Geocoding API."""
    reject_unknown_query_parameters(request, {"q"})
    return await location_service.search(query=q)
