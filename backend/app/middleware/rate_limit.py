"""Lightweight in-memory per-client API rate limiting middleware."""

from collections import defaultdict
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import Settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply fixed-window limits to expensive and externally backed API routes.

    This in-memory limiter is intended for a single backend instance. For multiple
    instances, use a shared store such as Redis.
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self._buckets: dict[tuple[str, str], tuple[int, float]] = {}
        self._lock = Lock()
        self._window_seconds = 60

    def _client_key(self, request: Request) -> str:
        if self.settings.rate_limit_trust_cf_connecting_ip:
            forwarded = request.headers.get("cf-connecting-ip", "").strip()
            if forwarded:
                return forwarded[:64]
        return request.client.host if request.client else "unknown"

    def _limits_for(self, request: Request) -> list[tuple[str, int]]:
        path = request.url.path
        method = request.method.upper()
        if method == "POST" and path in {
            "/api/v1/assistant/chat",
            "/api/v1/assistant/recommendations",
            "/api/v1/indoor/recommendations",
        }:
            return [("ai", self.settings.rate_limit_ai_per_minute)]
        if method == "GET" and path == "/api/v1/locations/search":
            return [("search", self.settings.rate_limit_search_per_minute)]
        if method == "GET" and path == "/api/v1/air-quality":
            limits = [("air_quality", self.settings.rate_limit_air_quality_per_minute)]
            if request.query_params.get("force_refresh", "").lower() in {"1", "true", "yes"}:
                limits.append(("force_refresh", self.settings.rate_limit_force_refresh_per_minute))
            return limits
        return []

    def _consume(self, client_key: str, bucket: str, limit: int) -> int | None:
        now = monotonic()
        key = (client_key, bucket)
        with self._lock:
            # Prune expired windows periodically without a background task.
            if len(self._buckets) > 4096:
                self._buckets = {
                    item_key: item
                    for item_key, item in self._buckets.items()
                    if now < item[1]
                }
            count, reset_at = self._buckets.get(key, (0, now + self._window_seconds))
            if now >= reset_at:
                count, reset_at = 0, now + self._window_seconds
            if count >= limit:
                return max(1, int(reset_at - now + 0.999))
            self._buckets[key] = (count + 1, reset_at)
            return None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        limits = self._limits_for(request)
        if not limits:
            return await call_next(request)

        client_key = self._client_key(request)
        retry_after = 0
        for bucket, limit in limits:
            blocked_for = self._consume(client_key, bucket, limit)
            if blocked_for is not None:
                retry_after = max(retry_after, blocked_for)

        if retry_after:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please wait before trying again.",
                    "error_code": "rate_limit_exceeded",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
