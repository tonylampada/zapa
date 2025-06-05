"""API v1 router for public endpoints."""

from fastapi import APIRouter

from .auth import router as auth_router
from .messages import router as messages_router
from .llm_config import router as llm_config_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(messages_router)
api_router.include_router(llm_config_router)
