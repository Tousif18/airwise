"""Top-level API v1 router."""

from fastapi import APIRouter

from app.api.routes import air_quality, family, health, locations

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(locations.router)
api_router.include_router(air_quality.router)
api_router.include_router(family.router)
