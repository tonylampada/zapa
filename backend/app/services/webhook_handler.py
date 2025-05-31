"""Webhook handler service for processing WhatsApp events."""

from typing import Dict, Any
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.schemas.webhook import (
    WhatsAppWebhookEvent,
    WebhookEventType,
    MessageReceivedData,
    MessageSentData,
    MessageFailedData,
    ConnectionStatusData
)
from app.schemas.message import MessageCreate, MessageDirection, MessageType
from app.services.message_service import MessageService
from app.services.agent_service import AgentService
from app.services.retry_handler import RetryHandler
from app.models import User
from app.config.private import settings

logger = logging.getLogger(__name__)


class WebhookHandlerService:
    """Service for handling WhatsApp webhook events."""
    
    def __init__(
        self,
        db: Session,
        message_service: MessageService,
        agent_service: AgentService
    ):
        self.db = db
        self.message_service = message_service
        self.agent_service = agent_service
        
    async def handle_webhook(self, event: WhatsAppWebhookEvent) -> Dict[str, Any]:
        """Process incoming webhook event."""
        logger.info(f"Processing webhook event: {event.event_type}")
        
        handlers = {
            WebhookEventType.MESSAGE_RECEIVED: self._handle_message_received,
            WebhookEventType.MESSAGE_SENT: self._handle_message_sent,
            WebhookEventType.MESSAGE_FAILED: self._handle_message_failed,
            WebhookEventType.CONNECTION_STATUS: self._handle_connection_status,
        }
        
        handler = handlers.get(event.event_type)
        if not handler:
            logger.warning(f"Unknown event type: {event.event_type}")
            return {"status": "ignored", "reason": "unknown_event_type"}
            
        return await handler(event)
    
    async def _handle_message_received(
        self, 
        event: WhatsAppWebhookEvent
    ) -> Dict[str, Any]:
        """Handle incoming message - either to system or to user's own number."""
        try:
            data = MessageReceivedData(**event.data)
            
            # Extract phone numbers from WhatsApp JID (format: +1234567890@s.whatsapp.net)
            from_phone = data.from_number.replace("@s.whatsapp.net", "")
            to_phone = data.to_number.replace("@s.whatsapp.net", "")
            
            # Get system number from settings (with fallback for tests)
            system_number = getattr(settings, 'WHATSAPP_SYSTEM_NUMBER', '+1234567890') if settings else '+1234567890'
            
            # Determine if this is a message TO the system or TO a user's number
            is_system_message = to_phone == system_number
            
            # Find or create user based on the appropriate phone number
            if is_system_message:
                # Message sent TO system FROM user
                user_phone = from_phone
            else:
                # Message sent TO user's number (user gave access to their WhatsApp)
                user_phone = to_phone
            
            user = self.db.query(User).filter(User.phone_number == user_phone).first()
            if not user:
                # Create new user
                user = User(
                    phone_number=user_phone,
                    display_name=f"User {user_phone[-4:]}",  # Default display name
                    is_active=True
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                logger.info(f"Created new user for phone: {user_phone}")
            
            # Determine message type
            if data.media_url:
                if data.media_type == "image":
                    message_type = MessageType.IMAGE
                elif data.media_type == "audio":
                    message_type = MessageType.AUDIO
                elif data.media_type == "video":
                    message_type = MessageType.VIDEO
                elif data.media_type == "document":
                    message_type = MessageType.DOCUMENT
                else:
                    message_type = MessageType.TEXT  # Fallback
            else:
                message_type = MessageType.TEXT
            
            # Create message metadata
            metadata = {
                "whatsapp_message_id": data.message_id,
                "timestamp": data.timestamp.isoformat(),
                "is_system_message": is_system_message
            }
            if data.media_url:
                metadata["media_url"] = data.media_url
                metadata["media_type"] = data.media_type
            
            # Determine direction based on message type
            if is_system_message:
                # Message TO system FROM user
                direction = MessageDirection.INCOMING
            else:
                # Message TO user's number - could be incoming or outgoing
                # If from the user's own number, it's outgoing
                # If from someone else to user's number, it's incoming
                if from_phone == user_phone:
                    direction = MessageDirection.OUTGOING
                else:
                    direction = MessageDirection.INCOMING
            
            # Store the message with actual JIDs
            message_create = MessageCreate(
                content=data.text or "",  # Empty string for media messages
                direction=direction,
                message_type=message_type,
                whatsapp_message_id=data.message_id,
                metadata=metadata,
                sender_jid=data.from_number,
                recipient_jid=data.to_number
            )
            
            message = await self.message_service.store_message(
                user_id=user.id,
                message_data=message_create
            )
            
            # Only trigger agent processing for text messages sent TO the system
            if is_system_message and data.text:
                try:
                    # Process with agent (non-critical - retry)
                    await RetryHandler.with_retry(
                        self.agent_service.process_message,
                        user_id=user.id,
                        message_content=data.text,
                        message_id=message.id,
                        max_retries=3,
                        delay=1.0,
                        backoff=2.0
                    )
                    return {"status": "processed", "message_id": message.id}
                except Exception as e:
                    logger.error(f"Agent processing failed after retries: {e}", exc_info=True)
                    # Return success anyway - we stored the message
                    return {"status": "stored", "message_id": message.id, "processing": "failed"}
            else:
                # Non-system message or non-text message, just store
                logger.info(f"Stored {'user' if not is_system_message else 'non-text'} message: {message.id}")
                return {"status": "stored", "message_id": message.id}
                
        except Exception as e:
            logger.error(f"Error handling message received: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def _handle_message_sent(
        self, 
        event: WhatsAppWebhookEvent
    ) -> Dict[str, Any]:
        """Handle confirmation of sent message."""
        try:
            data = MessageSentData(**event.data)
            
            # Update message status in database
            updated_message = await self.message_service.update_message_status(
                whatsapp_message_id=data.message_id,
                status=data.status
            )
            
            if updated_message:
                logger.info(f"Updated message status: {data.message_id} -> {data.status}")
                return {"status": "updated", "message_id": data.message_id}
            else:
                logger.warning(f"Message not found for update: {data.message_id}")
                return {"status": "not_found", "message_id": data.message_id}
                
        except Exception as e:
            logger.error(f"Error handling message sent: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def _handle_message_failed(
        self, 
        event: WhatsAppWebhookEvent
    ) -> Dict[str, Any]:
        """Handle failed message delivery."""
        try:
            data = MessageFailedData(**event.data)
            
            # Update message status with error
            updated_message = await self.message_service.update_message_status(
                whatsapp_message_id=data.message_id,
                status=f"failed: {data.error}"
            )
            
            if updated_message:
                logger.error(f"Message delivery failed: {data.message_id} - {data.error}")
                return {"status": "updated", "message_id": data.message_id, "error": data.error}
            else:
                logger.warning(f"Failed message not found: {data.message_id}")
                return {"status": "not_found", "message_id": data.message_id}
                
        except Exception as e:
            logger.error(f"Error handling message failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    async def _handle_connection_status(
        self, 
        event: WhatsAppWebhookEvent
    ) -> Dict[str, Any]:
        """Handle WhatsApp connection status updates."""
        try:
            data = ConnectionStatusData(**event.data)
            
            logger.info(f"WhatsApp connection status: {data.status} (session: {data.session_id})")
            
            # TODO: Could store in Redis or database for monitoring
            # For now, just log and acknowledge
            return {
                "status": "acknowledged",
                "connection_status": data.status,
                "session_id": data.session_id
            }
            
        except Exception as e:
            logger.error(f"Error handling connection status: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}