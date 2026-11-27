"""Shared validators for user-supplied location metadata."""

import math\nfrom zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_coordinate(value: float, axis: str) -> float:
    """Reject non-finite or out-of-range geographic coordinates."""
    limits = {"latitude": (-90.0, 90.0), "longitude": (-180.0, 180.0)}
    if axis not in limits:
        raise ValueError("Coordinate axis must be latitude or longitude.")
    if not math.isfinite(value):
        raise ValueError(f"{axis.capitalize()} must be a finite number.")
    lower, upper = limits[axis]
    if not lower <= value <= upper:
        raise ValueError(f"{axis.capitalize()} must be between {lower:g} and {upper:g}.")
    return value


def validate_timezone(value: str) -> str:
    """Accept Open-Meteo's auto value or a valid IANA timezone identifier."""
    cleaned = value.strip()
    if cleaned == "auto":
        return cleaned
    try:
        ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Timezone must be 'auto' or a valid IANA timezone name.") from None
    return cleaned
