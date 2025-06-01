"""API v1 router for public endpoints."""

from fastapi import APIRouter

from .auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)

# Add more routers here as they are created
# api_router.include_router(messages_router)
# api_router.include_router(sessions_router)
