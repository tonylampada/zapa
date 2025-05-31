"""Webhook endpoints for WhatsApp events."""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional

from app.schemas.webhook import WhatsAppWebhookEvent
from app.services.webhook_handler import WebhookHandlerService
from app.services.message_service import MessageService
from app.services.agent_service import AgentService
from app.core.database import get_db
from app.core.webhook_security import WebhookValidator
from app.core.config import get_settings
from sqlalchemy.orm import Session

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_webhook_handler(db: Session = Depends(get_db)) -> WebhookHandlerService:
    """Get webhook handler service instance."""
    message_service = MessageService(db)
    agent_service = AgentService(db)
    return WebhookHandlerService(db, message_service, agent_service)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    event: WhatsAppWebhookEvent,
    webhook_handler: WebhookHandlerService = Depends(get_webhook_handler),
    x_webhook_signature: Optional[str] = Header(None)
):
    """
    Receive webhook events from WhatsApp Bridge.
    
    Validates webhook signature if WEBHOOK_SECRET is configured.
    The Bridge service is on the internal network, so authentication
    is optional but recommended for production.
    """
    # Validate signature if secret is configured
    settings = get_settings()
    if hasattr(settings, 'WEBHOOK_SECRET') and settings.WEBHOOK_SECRET:
        validator = WebhookValidator(settings.WEBHOOK_SECRET)
        body = await request.body()
        
        if not validator.validate_signature(body, x_webhook_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
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