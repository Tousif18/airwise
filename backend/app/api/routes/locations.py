"""Location presets and geocoding search endpoints."""

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.schemas.air_quality import DataStatus, LocationSearchResponse
from app.services.locations import get_preset_locations, search_locations

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
) -> LocationSearchResponse:
    """Search matching cities via Open-Meteo Geocoding API."""
    return await search_locations(query=q, settings=get_settings())
