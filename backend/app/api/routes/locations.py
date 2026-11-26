"""Location presets and cached geocoding search endpoints."""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_location_search_service
from app.schemas.air_quality import DataStatus, LocationSearchResponse
from app.services.locations import LocationSearchService, get_preset_locations

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/presets", response_model=LocationSearchResponse)
async def list_preset_locations() -> LocationSearchResponse:
    """Return curated urban locations for instant dashboard monitoring."""
    return LocationSearchResponse(
        locations=get_preset_locations(),
        data_status=DataStatus.LIVE,
    )


@router.get("/search", response_model=LocationSearchResponse)
async def search_city_locations(
    q: str = Query(..., min_length=1, max_length=80, description="City or neighborhood name"),
    location_service: LocationSearchService = Depends(get_location_search_service),
) -> LocationSearchResponse:
    """Search matching cities via cached Open-Meteo Geocoding API."""
    return await location_service.search(query=q)
