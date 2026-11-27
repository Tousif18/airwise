"""System health and capability schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public capability and service status without exposing sensitive credentials."""

    status: str
    app_name: str
    environment: str
    open_meteo_configured: bool
    gemini_configured: bool
    gemini_model: str
    cache_ttl_seconds: int


class ReadinessResponse(BaseModel):
    """Local configuration checks used to decide whether the API can serve traffic."""

    status: str
    app_name: str
    environment: str
    checks: dict[str, bool]
