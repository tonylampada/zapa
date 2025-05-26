"""Health check endpoints for private API."""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.private import settings
from app.core.exceptions import DatabaseError, WhatsAppBridgeError
from app.database.connection import get_database_manager, get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.

    Returns basic service information without external dependencies.
    """
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """
    Comprehensive readiness check.

    Checks all external dependencies:
    - Database connectivity
    - WhatsApp Bridge connectivity
    """
    checks = {}
    overall_status = "ready"

    # Database check
    try:
        db_manager = get_database_manager()
        database_healthy = await db_manager.health_check()
        checks["database"] = {
            "status": "healthy" if database_healthy else "unhealthy",
            "url": settings.DATABASE_URL.split("@")[-1]
            if "@" in settings.DATABASE_URL
            else "masked",
        }
        if not database_healthy:
            overall_status = "not_ready"
            logger.error("Database health check failed")
    except Exception as e:
        checks["database"] = {
            "status": "error",
            "error": str(e),
        }
        overall_status = "not_ready"
        logger.error(f"Database check error: {e}")

    # WhatsApp Bridge check
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.WHATSAPP_BRIDGE_URL}/health")
            bridge_healthy = response.status_code == 200
            checks["whatsapp_bridge"] = {
                "status": "healthy" if bridge_healthy else "unhealthy",
                "url": settings.WHATSAPP_BRIDGE_URL,
                "response_code": str(response.status_code),
            }
            if not bridge_healthy:
                overall_status = "not_ready"
                logger.warning(f"WhatsApp Bridge unhealthy: {response.status_code}")
    except Exception as e:
        checks["whatsapp_bridge"] = {
            "status": "error",
            "error": str(e),
            "url": settings.WHATSAPP_BRIDGE_URL,
        }
        overall_status = "not_ready"
        logger.error(f"WhatsApp Bridge check error: {e}")

    response_data = {
        "status": overall_status,
        "service": settings.SERVICE_NAME,
        "checks": checks,
    }

    # Return 503 if not ready
    if overall_status != "ready":
        raise HTTPException(status_code=503, detail=response_data)

    return response_data


@router.get("/database")
async def database_check(
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """
    Detailed database connectivity check.

    Tests database connection and basic operations.
    """
    try:
        # Test basic query
        result = db.execute(text("SELECT 1 as test_value"))
        test_value = result.scalar()

        if test_value != 1:
            raise DatabaseError("Database query returned unexpected result")

        return {
            "status": "healthy",
            "database_url": settings.DATABASE_URL.split("@")[-1]
            if "@" in settings.DATABASE_URL
            else "masked",
            "connection_test": "passed",
        }

    except Exception as e:
        logger.error(f"Database check failed: {e}")
        raise DatabaseError(f"Database connectivity failed: {str(e)}") from e


@router.get("/whatsapp-bridge")
async def whatsapp_bridge_check() -> dict[str, Any]:
    """
    Detailed WhatsApp Bridge connectivity check.

    Tests connectivity to the WhatsApp Bridge service.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check health endpoint
            health_response = await client.get(f"{settings.WHATSAPP_BRIDGE_URL}/health")

            if health_response.status_code != 200:
                raise WhatsAppBridgeError(
                    f"Bridge health check failed with status {health_response.status_code}"
                )

            # Try to get bridge status if available
            try:
                status_response = await client.get(
                    f"{settings.WHATSAPP_BRIDGE_URL}/status"
                )
                bridge_data = (
                    status_response.json()
                    if status_response.status_code == 200
                    else None
                )
            except Exception:
                bridge_data = None

            return {
                "status": "healthy",
                "bridge_url": settings.WHATSAPP_BRIDGE_URL,
                "health_check": "passed",
                "bridge_data": bridge_data,
            }

    except httpx.RequestError as e:
        logger.error(f"WhatsApp Bridge connection error: {e}")
        raise WhatsAppBridgeError(
            f"Failed to connect to WhatsApp Bridge: {str(e)}"
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp Bridge HTTP error: {e}")
        raise WhatsAppBridgeError(
            f"WhatsApp Bridge returned error: {e.response.status_code}"
        ) from e
    except Exception as e:
        logger.error(f"WhatsApp Bridge check failed: {e}")
        raise WhatsAppBridgeError(f"WhatsApp Bridge check failed: {str(e)}") from e
