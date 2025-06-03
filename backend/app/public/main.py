"""FastAPI application for Zapa Public entrypoint."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.public import settings

# from app.core.logging import setup_logging  # TODO: Add logging module
# from app.database.connection import DatabaseManager  # TODO: Fix import
from app.public.api.v1.router import api_router

# Set up logging - TODO: Add logging module
# setup_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info("Starting Zapa Public entrypoint...")

    # Get database manager - TODO: Fix DatabaseManager import
    # database_manager = DatabaseManager(settings.DATABASE_URL)

    # Test database connection
    # try:
    #     database_manager.get_session()
    #     logger.info("Database connection successful")
    # except Exception as e:
    #     logger.error(f"Database connection failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Zapa Public entrypoint...")


app = FastAPI(
    title="Zapa Public API",
    description="Public API for WhatsApp agent data access",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS middleware - configured for public frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Health check endpoints
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "zapa-public",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
