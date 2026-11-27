"""Inbound request-size protection for AI endpoints."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies on AI endpoints before route validation."""

    MAX_BODY_BYTES = 64 * 1024
    PROTECTED_PATHS = {
        "/api/v1/assistant/chat",
        "/api/v1/assistant/recommendations",
        "/api/v1/indoor/recommendations",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method.upper() == "POST" and request.url.path in self.PROTECTED_PATHS:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > self.MAX_BODY_BYTES:
                        return self._too_large()
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header."},
                    )

            body = await request.body()
            if len(body) > self.MAX_BODY_BYTES:
                return self._too_large()

        return await call_next(request)

    @staticmethod
    def _too_large() -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "detail": "Request body is too large. Maximum size is 64 KB.",
                "error_code": "request_body_too_large",
            },
        )
