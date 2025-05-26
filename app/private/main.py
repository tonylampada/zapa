"""FastAPI application for Zapa Private entrypoint."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config.private import settings
from app.core.exceptions import ZapaException
from app.core.logging import setup_logging
from app.database.connection import get_database_manager
from app.private.api.v1.router import api_router

# Set up logging
setup_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Zapa Private entrypoint...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Get database manager
    database_manager = get_database_manager(settings)

    # Test database connection
    try:
        if await database_manager.health_check():
            logger.info("Database connection successful")
        else:
            logger.error("Database connection failed!")
    except Exception as e:
        logger.error(f"Database connection error: {e}")

    # Store database manager in app state for cleanup
    app.state.database_manager = database_manager

    yield

    # Shutdown
    logger.info("Shutting down Zapa Private entrypoint...")
    if hasattr(app.state, "database_manager"):
        await app.state.database_manager.close()


app = FastAPI(
    title="Zapa Private API",
    description="Internal API for WhatsApp agent management",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# Security middleware
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.internal.company.com"],
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Add request timing headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests."""
    start_time = time.time()

    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
        },
    )

    response = await call_next(request)

    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} in {process_time:.3f}s",
        extra={
            "status_code": response.status_code,
            "process_time": process_time,
        },
    )

    return response


# Exception handlers
@app.exception_handler(ZapaException)
async def zapa_exception_handler(request: Request, exc: ZapaException):
    """Handle custom Zapa exceptions."""
    logger.error(f"Zapa exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": {}
            if settings.ENVIRONMENT == "production"
            else {"exception": str(exc)},
        },
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Zapa Private API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs" if settings.ENVIRONMENT != "production" else None,
    }
