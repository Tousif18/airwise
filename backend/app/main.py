"""FastAPI application entry point for the AirWise backend."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_size_limit import RequestSizeLimitMiddleware


HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "request_body_too_large",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
    503: "service_unavailable",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="Modular AirWise API for Open-Meteo air quality monitoring, household guidance, and indoor protection.",
    )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request, exc: StarletteHTTPException) -> JSONResponse:
        """Keep FastAPI's detail payload while adding a stable machine-readable code."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": HTTP_ERROR_CODES.get(exc.status_code, "http_error"),
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return the standard validation details with a consistent error code."""
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "error_code": "validation_error"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )

    app.add_middleware(RequestSizeLimitMiddleware)

    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware, settings=settings)

    app.include_router(api_router)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()


if __name__ == "__main__":
    runtime_settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=runtime_settings.resolved_host,
        port=runtime_settings.backend_port,
    )
