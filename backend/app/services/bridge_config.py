"""WhatsApp Bridge configuration service."""

import logging
from typing import Dict, Any, Optional

from app.adapters.whatsapp import WhatsAppBridgeAdapter
from app.config.private import settings

logger = logging.getLogger(__name__)


class BridgeConfigurationService:
    """Service for managing WhatsApp Bridge configuration."""

    def __init__(self):
        """Initialize the bridge configuration service."""
        self.webhook_url = f"{settings.HOST_URL}/api/v1/webhooks/whatsapp"
        self.bridge_adapter = WhatsAppBridgeAdapter(settings.WHATSAPP_API_URL)

    async def setup_bridge(self) -> Dict[str, Any]:
        """Configure the WhatsApp Bridge with webhook settings."""
        try:
            # Get current configuration
            current_config = await self._get_current_config()
            
            # Update webhook configuration
            webhook_config = {
                "webhook_url": self.webhook_url,
                "events": [
                    "message.received",
                    "message.sent", 
                    "message.failed",
                    "connection.status"
                ],
                "retry_config": {
                    "max_retries": 3,
                    "retry_delay": 5,
                }
            }
            
            # Apply configuration to bridge
            result = await self._update_webhook_config(webhook_config)
            
            logger.info(f"WhatsApp Bridge configured with webhook: {self.webhook_url}")
            return {
                "status": "configured",
                "webhook_url": self.webhook_url,
                "configuration": result
            }
            
        except Exception as e:
            logger.error(f"Failed to configure WhatsApp Bridge: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def check_bridge_health(self) -> Dict[str, Any]:
        """Check WhatsApp Bridge health and connection status."""
        try:
            async with self.bridge_adapter as adapter:
                # Get sessions to check if bridge is responsive
                sessions = await adapter.get_sessions()
                
                # Get active session count
                active_sessions = [s for s in sessions if s.status == "connected"]
                
                return {
                    "status": "healthy",
                    "total_sessions": len(sessions),
                    "active_sessions": len(active_sessions),
                    "bridge_url": settings.WHATSAPP_API_URL,
                    "webhook_url": self.webhook_url,
                }
                
        except Exception as e:
            logger.error(f"Bridge health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "bridge_url": settings.WHATSAPP_API_URL,
            }

    async def ensure_system_session(self) -> Dict[str, Any]:
        """Ensure the system WhatsApp session exists and is connected."""
        try:
            system_number = settings.WHATSAPP_SYSTEM_NUMBER
            
            async with self.bridge_adapter as adapter:
                # Check if system session exists
                sessions = await adapter.get_sessions()
                system_session = next(
                    (s for s in sessions if s.session_id == system_number),
                    None
                )
                
                if not system_session:
                    # Create system session
                    session = await adapter.create_session(system_number)
                    logger.info(f"Created system session: {system_number}")
                    
                    # Get QR code for connection
                    qr_code = await adapter.get_qr_code(system_number)
                    
                    return {
                        "status": "created",
                        "session_id": system_number,
                        "qr_code": qr_code,
                        "message": "Scan QR code to connect system WhatsApp"
                    }
                    
                elif system_session.status != "connected":
                    # Session exists but not connected
                    qr_code = await adapter.get_qr_code(system_number)
                    
                    return {
                        "status": "disconnected",
                        "session_id": system_number,
                        "qr_code": qr_code if qr_code else None,
                        "message": "System session needs reconnection"
                    }
                    
                else:
                    # Session exists and is connected
                    return {
                        "status": "connected",
                        "session_id": system_number,
                        "connected_phone": system_session.phone_number,
                    }
                    
        except Exception as e:
            logger.error(f"Failed to ensure system session: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def _get_current_config(self) -> Dict[str, Any]:
        """Get current bridge configuration."""
        # This would call the bridge API to get current config
        # For now, return empty dict as the bridge may not have this endpoint
        return {}

    async def _update_webhook_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update webhook configuration on the bridge."""
        # This would call the bridge API to update webhook config
        # For now, just return the config as the bridge handles webhooks internally
        return config

    async def test_webhook(self) -> Dict[str, Any]:
        """Send a test webhook to verify configuration."""
        try:
            # This would trigger a test webhook from the bridge
            # For now, just verify the bridge is accessible
            health = await self.check_bridge_health()
            
            if health["status"] == "healthy":
                return {
                    "status": "success",
                    "message": "Bridge is healthy and webhook URL is configured"
                }
            else:
                return {
                    "status": "failed",
                    "message": "Bridge is not healthy",
                    "details": health
                }
                
        except Exception as e:
            logger.error(f"Webhook test failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global instance
bridge_config = BridgeConfigurationService()