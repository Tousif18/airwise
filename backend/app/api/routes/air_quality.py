"""Air quality overview endpoints backed by Open-Meteo."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.dependencies import get_air_quality_service
from app.schemas.air_quality import AirQualityOverviewResponse
from app.services.locations import resolve_location_selection

router = APIRouter(prefix="/air-quality", tags=["air-quality"])

_ALLOWED_QUERY_PARAMETERS = {
    "location_id",
    "latitude",
    "longitude",
    "name",
    "region",
    "country",
    "timezone",
    "force_refresh",
}


@router.get("", response_model=AirQualityOverviewResponse)
async def get_air_quality_overview(
    request: Request,
    location_id: str | None = Query(default=None, description="Preset location ID"),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    name: str | None = Query(default=None, max_length=120),
    region: str = Query(default="", max_length=120),
    country: str = Query(default="", max_length=120),
    timezone: str = Query(default="auto", max_length=64),
    force_refresh: bool = Query(default=False, description="Bypass TTL cache for live fetch"),
) -> AirQualityOverviewResponse:
    """Return live, cached, or explicitly unavailable air quality data."""
    unknown_parameters = sorted(set(request.query_params.keys()) - _ALLOWED_QUERY_PARAMETERS)
    if unknown_parameters:
        names = ", ".join(unknown_parameters)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown query parameter(s): {names}.",
        )

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Both latitude and longitude must be provided together.",
        )
    if location_id and latitude is not None and longitude is not None:
        raise HTTPException(
            status_code=422,
            detail="Choose either location_id or custom coordinates, not both.",
        )

    location = resolve_location_selection(
        location_id=location_id,
        latitude=latitude,
        longitude=longitude,
        name=name,
        region=region,
        country=country,
        timezone=timezone,
    )
    if location is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown preset location_id '{location_id}'. Provide latitude and longitude for custom locations.",
        )

    service = get_air_quality_service()
    return await service.get_air_quality(location=location, force_refresh=force_refresh)
