"""Main API router for private v1 endpoints."""
from fastapi import APIRouter

from app.private.api.v1.health import router as health_router
from app.private.api.v1.auth import router as auth_router
from app.private.api.v1.admin.users import router as admin_users_router
from app.private.api.v1.admin.llm_config import router as admin_llm_router
from app.private.api.v1.admin.system import router as admin_system_router
from app.private.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

# Include health check routes
api_router.include_router(
    health_router,
    tags=["health"],
)

# Include authentication routes
api_router.include_router(
    auth_router,
    tags=["auth"],
)

# Include admin routes
api_router.include_router(admin_users_router)
api_router.include_router(admin_llm_router)
api_router.include_router(admin_system_router)

# Include webhook routes
api_router.include_router(
    webhooks_router,
    tags=["webhooks"],
)
