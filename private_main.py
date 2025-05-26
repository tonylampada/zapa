from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.private import settings

app = FastAPI(
    title="Zapa Private API",
    description="Internal service for WhatsApp agent management",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS for admin frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add checks for database, redis, whatsapp bridge
    return {
        "status": "ready",
        "service": settings.SERVICE_NAME,
    }
