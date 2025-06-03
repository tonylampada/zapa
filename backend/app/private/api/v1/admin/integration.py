"""Admin API endpoints for WhatsApp integration management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_admin
from app.models import User
from app.services.bridge_config import bridge_config
from app.services.integration_monitor import integration_monitor
from app.services.integration_orchestrator import integration_orchestrator
from app.services.message_queue import message_queue

router = APIRouter()


@router.get("/status")
async def get_integration_status(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Get overall integration status."""
    try:
        integration_status = await integration_orchestrator.get_status()
        return integration_status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get integration status: {str(e)}",
        ) from e


@router.post("/initialize")
async def initialize_integration(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Initialize WhatsApp integration components."""
    try:
        result = await integration_orchestrator.initialize()
        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Integration initialization failed: {result.get('error', 'Unknown error')}",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize integration: {str(e)}",
        ) from e


@router.post("/shutdown")
async def shutdown_integration(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Shutdown WhatsApp integration components."""
    try:
        result = await integration_orchestrator.shutdown()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to shutdown integration: {str(e)}",
        ) from e


@router.post("/reinitialize")
async def reinitialize_integration(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Reinitialize WhatsApp integration (shutdown and restart)."""
    try:
        result = await integration_orchestrator.reinitialize()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reinitialize integration: {str(e)}",
        ) from e


@router.get("/health")
async def get_integration_health(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Get detailed health status of all components."""
    try:
        health = await integration_monitor.get_system_health()
        return health
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get health status: {str(e)}",
        ) from e


@router.get("/health/{component}")
async def get_component_health(
    component: str,
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Get health status of a specific component."""
    try:
        health = await integration_monitor.get_component_health(component)
        if not health:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Component '{component}' not found"
            )
        return health
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get component health: {str(e)}",
        ) from e


@router.get("/queue/stats")
async def get_queue_statistics(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Get message queue statistics."""
    try:
        stats = await message_queue.get_queue_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue statistics: {str(e)}",
        ) from e


@router.post("/queue/clear-failed")
async def clear_failed_messages(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Clear all failed messages from the queue."""
    try:
        count = await message_queue.clear_failed()
        return {"cleared": count, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear failed messages: {str(e)}",
        ) from e


@router.post("/queue/requeue-failed")
async def requeue_failed_messages(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Requeue all failed messages for retry."""
    try:
        count = await message_queue.requeue_failed()
        return {"requeued": count, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to requeue messages: {str(e)}",
        ) from e


@router.get("/bridge/health")
async def get_bridge_health(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Get WhatsApp Bridge health status."""
    try:
        health = await bridge_config.check_bridge_health()
        return health
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check bridge health: {str(e)}",
        ) from e


@router.post("/bridge/ensure-system-session")
async def ensure_system_session(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Ensure system WhatsApp session is connected."""
    try:
        result = await bridge_config.ensure_system_session()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ensure system session: {str(e)}",
        ) from e


@router.post("/bridge/test-webhook")
async def test_webhook(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Test webhook connectivity."""
    try:
        result = await bridge_config.test_webhook()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {str(e)}",
        ) from e
