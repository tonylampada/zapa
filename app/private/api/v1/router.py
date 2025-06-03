"""Main API router for private v1 endpoints."""

from fastapi import APIRouter

from app.private.api.v1.health import router as health_router

api_router = APIRouter()

# Include health check routes
api_router.include_router(
    health_router,
    tags=["health"],
)
