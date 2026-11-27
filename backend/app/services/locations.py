"""Preset urban monitoring locations and cached Open-Meteo geocoding lookup."""

import asyncio
from datetime import datetime, timezone
import math
import random
import logging
import httpx

from app.core.config import Settings
from app.schemas.air_quality import DataStatus, LocationOption, LocationSearchResponse
from app.services.cache import AsyncRequestCoalescer, TTLCache
from app.services.open_meteo import parse_retry_after_seconds

logger = logging.getLogger(__name__)

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
    """Resolve coordinates, preset ID, or default Kolkata location."""
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


class LocationSearchService:
    """Cached and coalesced Open-Meteo geocoding lookup with 429 protection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: TTLCache[LocationSearchResponse] = TTLCache(
            ttl_seconds=settings.geocoding_cache_ttl_seconds
        )
        self._rate_limit_cache: TTLCache[int] = TTLCache(
            ttl_seconds=settings.air_quality_rate_limit_cooldown_seconds
        )
        self._coalescer: AsyncRequestCoalescer[LocationSearchResponse] = (
            AsyncRequestCoalescer()
        )

    async def search(
        self,
        query: str,
        client: httpx.AsyncClient | None = None,
    ) -> LocationSearchResponse:
        """Search locations via Open-Meteo Geocoding API with caching and coalescing."""
        cleaned = query.strip()
        if len(cleaned) < 2:
            return LocationSearchResponse(
                locations=PRESET_LOCATIONS,
                data_status=DataStatus.LIVE,
            )

        key = cleaned.lower()
        cached = self._cache.get(key)
        if cached is not None:
            return cached.value.model_copy(update={"data_status": DataStatus.CACHED})

        rate_entry = self._rate_limit_cache.get(key)
        if rate_entry is not None:
            now = datetime.now(timezone.utc)
            remaining = max(1, math.ceil((rate_entry.expires_at - now).total_seconds()))
            return LocationSearchResponse(
                locations=[],
                data_status=DataStatus.UNAVAILABLE,
                rate_limited=True,
                retry_after_seconds=remaining,
                error_detail=(
                    f"Open-Meteo Geocoding rate limit reached (HTTP 429). "
                    f"Please wait ~{remaining}s before searching again."
                ),
            )

        async def _execute_search() -> LocationSearchResponse:
            fresh = self._cache.get(key)
            if fresh is not None:
                return fresh.value.model_copy(update={"data_status": DataStatus.CACHED})

            params = {
                "name": cleaned,
                "count": 6,
                "language": "en",
                "format": "json",
            }
            owns_client = client is None
            active_client = client or httpx.AsyncClient(
                timeout=self._settings.http_timeout_seconds
            )
            max_retries = max(0, self._settings.air_quality_max_retries)
            base_delay = max(0.0, self._settings.air_quality_retry_base_delay_seconds)
            max_delay = max(base_delay, self._settings.air_quality_retry_max_delay_seconds)

            try:
                payload = None
                for attempt in range(max_retries + 1):
                    try:
                        response = await active_client.get(
                            self._settings.open_meteo_geocoding_url,
                            params=params,
                        )
                    except (httpx.TimeoutException, httpx.TransportError) as exc:
                        if attempt < max_retries:
                            delay = min(
                                max_delay,
                                base_delay * (2 ** attempt) + random.uniform(0.0, 0.2),
                            )
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        logger.warning(
                            "Open-Meteo geocoding request failed after retries (%s)",
                            type(exc).__name__,
                        )
                        return LocationSearchResponse(
                            locations=[],
                            data_status=DataStatus.UNAVAILABLE,
                            error_detail="Location search is temporarily unavailable. Please try again.",
                        )

                    if response.status_code == 429:
                        retry_after = parse_retry_after_seconds(
                            response.headers.get("retry-after")
                        )
                        effective_retry = (
                            retry_after
                            or self._settings.air_quality_rate_limit_cooldown_seconds
                        )
                        if attempt < max_retries and (retry_after is None or retry_after <= max_delay):
                            delay = min(
                                max_delay,
                                max(retry_after or 0, base_delay * (2 ** attempt)),
                            )
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        self._rate_limit_cache.set(
                            key, effective_retry, ttl_seconds=effective_retry
                        )
                        return LocationSearchResponse(
                            locations=[],
                            data_status=DataStatus.UNAVAILABLE,
                            rate_limited=True,
                            retry_after_seconds=effective_retry,
                            error_detail=(
                                f"Open-Meteo Geocoding rate limit reached (HTTP 429). "
                                f"Please wait ~{effective_retry}s before searching again."
                            ),
                        )

                    if response.status_code >= 500 and attempt < max_retries:
                        delay = min(max_delay, base_delay * (2 ** attempt))
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue

                    try:
                        response.raise_for_status()
                        payload = response.json()
                    except (httpx.HTTPError, ValueError) as exc:
                        logger.warning(
                            "Open-Meteo geocoding response could not be processed (%s)",
                            type(exc).__name__,
                        )
                        return LocationSearchResponse(
                            locations=[],
                            data_status=DataStatus.UNAVAILABLE,
                            error_detail="Location search is temporarily unavailable. Please try again.",
                        )
                    break

                if not isinstance(payload, dict):
                    logger.warning(
                        "Open-Meteo geocoding returned an unexpected payload type (%s)",
                        type(payload).__name__,
                    )
                    return LocationSearchResponse(
                        locations=[],
                        data_status=DataStatus.UNAVAILABLE,
                        error_detail="Location search is temporarily unavailable. Please try again.",
                    )

                raw_results = payload.get("results")
                if raw_results is None:
                    raw_results = []
                elif not isinstance(raw_results, list):
                    logger.warning("Open-Meteo geocoding results field was not a list")
                    return LocationSearchResponse(
                        locations=[],
                        data_status=DataStatus.UNAVAILABLE,
                        error_detail="Location search is temporarily unavailable. Please try again.",
                    )

                locations: list[LocationOption] = []
                for idx, item in enumerate(raw_results):
                    if not isinstance(item, dict):
                        logger.warning("Skipping malformed geocoding result at index %s", idx)
                        continue
                    try:
                        if "latitude" not in item or "longitude" not in item:
                            raise ValueError("Missing coordinates")
                        locations.append(
                            LocationOption(
                                id=f"geo-{item.get('id', idx)}",
                                name=item.get("name") if isinstance(item.get("name"), str) else "Unknown",
                                region=item.get("admin1") if isinstance(item.get("admin1"), str) else "",
                                country=item.get("country") if isinstance(item.get("country"), str) else "",
                                latitude=float(item["latitude"]),
                                longitude=float(item["longitude"]),
                                timezone=item.get("timezone") if isinstance(item.get("timezone"), str) else "auto",
                            )
                        )
                    except (TypeError, ValueError):
                        logger.warning("Skipping geocoding result with invalid fields at index %s", idx)
                        continue

                result = LocationSearchResponse(
                    locations=locations,
                    data_status=DataStatus.LIVE,
                )
                self._cache.set(key, result)
                return result
            finally:
                if owns_client:
                    await active_client.aclose()

        return await self._coalescer.run(key, _execute_search)


async def search_locations(
    query: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> LocationSearchResponse:
    """Stateless wrapper preserved for direct service calls and tests."""
    return await LocationSearchService(settings).search(query=query, client=client)
