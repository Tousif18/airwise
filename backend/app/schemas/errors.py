"""Reusable response models for machine-readable API errors."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard HTTP error envelope; detail retains its endpoint-specific shape."""

    detail: Any
    error_code: str


class RateLimitErrorResponse(ErrorResponse):
    """Rate-limit response including the retry delay."""

    detail: str
    error_code: str = "rate_limit_exceeded"
    retry_after_seconds: int
