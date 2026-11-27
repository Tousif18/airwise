"""Shared validators for user-supplied location metadata."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
