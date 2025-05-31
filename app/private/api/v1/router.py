"""Main API router for private v1 endpoints."""
from fastapi import APIRouter

from app.private.api.v1.health import router as health_router

api_router = APIRouter()

# Include health check routes
api_router.include_router(
    health_router,
    tags=["health"],
)

# TODO: Add other routers as they are implemented
# api_router.include_router(auth_router, tags=["auth"])
# api_router.include_router(admin_users_router)
# api_router.include_router(admin_llm_router)
# api_router.include_router(admin_system_router)
# api_router.include_router(webhooks_router, tags=["webhooks"])
