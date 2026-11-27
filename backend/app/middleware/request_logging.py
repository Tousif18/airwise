"""Privacy-safe request logging and correlation IDs."""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("airwise.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request metadata without recording user input or sensitive headers."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = uuid4().hex
        started_at = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            logger.error(
                "request_failed request_id=%s method=%s path=%s exception_type=%s",
                request_id,
                request.method,
                request.url.path,
                type(exc).__name__,
            )
            raise
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "request_completed request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response
