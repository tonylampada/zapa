"""Webhook endpoints for WhatsApp events."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.webhook import WhatsAppWebhookEvent
from app.services.webhook_handler import WebhookHandlerService
from app.services.message_service import MessageService
from app.services.agent_service import AgentService
from app.core.database import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_webhook_handler(db: Session = Depends(get_db)) -> WebhookHandlerService:
    """Get webhook handler service instance."""
    message_service = MessageService(db)
    agent_service = AgentService(db)
    return WebhookHandlerService(db, message_service, agent_service)


@router.post("/whatsapp")
async def whatsapp_webhook(
    event: WhatsAppWebhookEvent,
    webhook_handler: WebhookHandlerService = Depends(get_webhook_handler)
):
    """
    Receive webhook events from WhatsApp Bridge.
    
    The Bridge service is on the internal network, so no authentication
    is required. Network isolation provides security.
    """
    try:
        result = await webhook_handler.handle_webhook(event)
        return result
    except Exception as e:
        # Log but don't fail - webhook delivery is critical
        import logging
        logging.error(f"Webhook processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/whatsapp/health")
async def webhook_health():
    """Health check endpoint for webhook service."""
    return {"status": "healthy", "service": "webhook_handler"}