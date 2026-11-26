"""Backend configuration loaded strictly from environment variables."""

from functools import lru_cache
import os
from pathlib import Path
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings sourced from environment variables or optional local .env."""

    app_name: str = "AirWise API"
    app_env: str = "development"
    backend_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("BACKEND_HOST", "HOST"),
    )
    backend_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "BACKEND_PORT"),
    )

    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    frontend_url: str | None = Field(default=None, alias="FRONTEND_URL")
    cors_origin_regex: str | None = Field(default=None, alias="CORS_ORIGIN_REGEX")

    open_meteo_air_quality_url: str = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
    )
    open_meteo_geocoding_url: str = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )
    air_quality_cache_ttl_seconds: int = 600
    air_quality_stale_warning_seconds: int = 300
    air_quality_observation_stale_minutes: int = 180
    air_quality_rate_limit_cooldown_seconds: int = 60
    air_quality_max_retries: int = 2
    air_quality_retry_base_delay_seconds: float = 0.5
    air_quality_retry_max_delay_seconds: float = 4.0
    geocoding_cache_ttl_seconds: int = 3600
    http_timeout_seconds: float = 10.0

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_models_raw: str = Field(
        default="gemini-3.5-flash,gemini-3.5-flash-lite",
        alias="GEMINI_FALLBACK_MODELS",
    )
    gemini_timeout_seconds: float = 25.0

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("frontend_url", "cors_origin_regex", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        """Convert blank env values like '' to None so CORSMiddleware never compiles ''."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    @property
    def resolved_host(self) -> str:
        """Bind 0.0.0.0 in production or cloud runtimes injecting PORT."""
        if self.app_env.lower() == "production" or "PORT" in os.environ:
            if self.backend_host in ("127.0.0.1", "localhost", ""):
                return "0.0.0.0"
        return self.backend_host

    @property
    def gemini_fallback_models(self) -> list[str]:
        """Parse comma-separated fallback Gemini models for transient 503/504 errors."""
        return [
            model.strip()
            for model in self.gemini_fallback_models_raw.split(",")
            if model.strip() and model.strip() != self.gemini_model
        ]

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins and optional FRONTEND_URL cleanly."""
        origins: list[str] = []
        seen: set[str] = set()
        for raw in self.cors_origins_raw.split(","):
            cleaned = raw.strip().rstrip("/")
            if cleaned and cleaned not in seen:
                origins.append(cleaned)
                seen.add(cleaned)
        if self.frontend_url:
            cleaned_fe = self.frontend_url.strip().rstrip("/")
            if cleaned_fe and cleaned_fe not in seen:
                origins.append(cleaned_fe)
                seen.add(cleaned_fe)
        return origins

    @property
    def gemini_configured(self) -> bool:
        """Return True only when a non-empty Gemini API key is configured."""
        return bool(self.gemini_api_key and self.gemini_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
