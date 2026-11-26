"""Preset urban monitoring locations and Open-Meteo geocoding lookup."""

import httpx

from app.core.config import Settings
from app.schemas.air_quality import DataStatus, LocationOption, LocationSearchResponse

PRESET_LOCATIONS: list[LocationOption] = [
    LocationOption(
        id="kolkata-in",
        name="Kolkata",
        region="West Bengal",
        country="India",
        latitude=22.5726,
        longitude=88.3639,
        timezone="Asia/Kolkata",
    ),
    LocationOption(
        id="new-delhi-in",
        name="New Delhi",
        region="Delhi NCR",
        country="India",
        latitude=28.6139,
        longitude=77.2090,
        timezone="Asia/Kolkata",
    ),
    LocationOption(
        id="gurugram-in",
        name="Gurugram",
        region="Haryana",
        country="India",
        latitude=28.4595,
        longitude=77.0266,
        timezone="Asia/Kolkata",
    ),
    LocationOption(
        id="mumbai-in",
        name="Mumbai",
        region="Maharashtra",
        country="India",
        latitude=19.0760,
        longitude=72.8777,
        timezone="Asia/Kolkata",
    ),
    LocationOption(
        id="bengaluru-in",
        name="Bengaluru",
        region="Karnataka",
        country="India",
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
    ),
    LocationOption(
        id="lahore-pk",
        name="Lahore",
        region="Punjab",
        country="Pakistan",
        latitude=31.5204,
        longitude=74.3587,
        timezone="Asia/Karachi",
    ),
    LocationOption(
        id="london-gb",
        name="London",
        region="Greater London",
        country="United Kingdom",
        latitude=51.5072,
        longitude=-0.1276,
        timezone="Europe/London",
    ),
]


def get_preset_locations() -> list[LocationOption]:
    """Return curated preset cities for quick selection."""
    return PRESET_LOCATIONS


def find_preset_location(location_id: str) -> LocationOption | None:
    """Find a preset location by ID."""
    for loc in PRESET_LOCATIONS:
        if loc.id == location_id:
            return loc
    return None


def resolve_location_selection(
    location_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    name: str | None = None,
    region: str = "",
    country: str = "",
    timezone: str = "auto",
) -> LocationOption | None:
    """Resolve coordinates, preset ID, or default Kolkata location.

    Returns None when an explicit unknown preset `location_id` is supplied without coordinates.
    """
    if latitude is not None and longitude is not None:
        return LocationOption(
            id=location_id or f"custom-{round(latitude, 3)}-{round(longitude, 3)}",
            name=name or f"{latitude:.2f}, {longitude:.2f}",
            region=region,
            country=country or "Custom Coordinates",
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )
    if location_id:
        return find_preset_location(location_id)
    return PRESET_LOCATIONS[0]


async def search_locations(
    query: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> LocationSearchResponse:
    """Search locations via Open-Meteo Geocoding API with honest error handling."""
    cleaned = query.strip()
    if len(cleaned) < 2:
        return LocationSearchResponse(
            locations=PRESET_LOCATIONS,
            data_status=DataStatus.LIVE,
        )

    params = {
        "name": cleaned,
        "count": 6,
        "language": "en",
        "format": "json",
    }

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    try:
        response = await active_client.get(settings.open_meteo_geocoding_url, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return LocationSearchResponse(
            locations=[],
            data_status=DataStatus.UNAVAILABLE,
            error_detail=f"Location search unavailable: {exc}",
        )
    finally:
        if owns_client:
            await active_client.aclose()

    raw_results = payload.get("results") or []
    locations = [
        LocationOption(
            id=f"geo-{item.get('id', idx)}",
            name=item.get("name", "Unknown"),
            region=item.get("admin1") or "",
            country=item.get("country") or "",
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
            timezone=item.get("timezone") or "auto",
        )
        for idx, item in enumerate(raw_results)
        if "latitude" in item and "longitude" in item
    ]

    return LocationSearchResponse(
        locations=locations,
        data_status=DataStatus.LIVE,
    )
