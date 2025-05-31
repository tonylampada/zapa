"""Integration tests for complete webhook processing flow."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock

from sqlalchemy.orm import Session

from app.services.webhook_handler import WebhookHandlerService
from app.services.message_service import MessageService
from app.services.agent_service import AgentService
from app.schemas.webhook import WhatsAppWebhookEvent, WebhookEventType
from app.models import User, Message, LLMConfig


@pytest.mark.integration
@pytest.mark.asyncio
class TestWebhookIntegration:
    """Test complete webhook processing flow with real database."""
    
    async def test_full_webhook_flow(self, test_db: Session):
        """Test complete webhook processing flow."""
        # Create services
        message_service = MessageService(test_db)
        agent_service = AgentService(test_db)
        webhook_handler = WebhookHandlerService(test_db, message_service, agent_service)
        
        # Create webhook event
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow(),
            "data": {
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_test_123",
                "text": "Hello, can you help me?",
                "timestamp": datetime.utcnow()
            }
        }
        
        event = WhatsAppWebhookEvent(**event_data)
        
        # Mock agent processing to avoid OpenAI calls
        with patch.object(agent_service, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = None
            
            # Process webhook
            result = await webhook_handler.handle_webhook(event)
        
        assert result["status"] == "processed"
        assert "message_id" in result
        
        # Verify user was created
        user = test_db.query(User).filter(User.phone_number == "+1234567890").first()
        assert user is not None
        assert user.display_name == "User 7890"
        
        # Verify message was stored
        message = test_db.query(Message).filter(
            Message.media_metadata.op("->>")("whatsapp_message_id") == "msg_test_123"
        ).first()
        assert message is not None
        assert message.content == "Hello, can you help me?"
        assert message.user_id == user.id
        assert message.sender_jid == "+1234567890@s.whatsapp.net"
        
        # Verify agent was called
        mock_process.assert_called_once_with(
            user_id=user.id,
            message_content="Hello, can you help me?",
            message_id=message.id
        )
    
    async def test_webhook_retry_on_failure(self, test_db: Session):
        """Test retry logic when agent processing fails."""
        message_service = MessageService(test_db)
        agent_service = AgentService(test_db)
        webhook_handler = WebhookHandlerService(test_db, message_service, agent_service)
        
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow(),
            "data": {
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_retry_test",
                "text": "Test retry",
                "timestamp": datetime.utcnow()
            }
        }
        
        event = WhatsAppWebhookEvent(**event_data)
        
        # Mock agent to fail twice then succeed
        call_count = 0
        
        async def failing_process_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return None
        
        with patch.object(agent_service, 'process_message', new=failing_process_message):
            with patch('asyncio.sleep'):  # Speed up test by not actually sleeping
                result = await webhook_handler.handle_webhook(event)
        
        assert result["status"] == "processed"
        assert call_count == 3  # Failed twice, succeeded on third
        
        # Verify message was still stored
        message = test_db.query(Message).filter(
            Message.media_metadata.op("->>")("whatsapp_message_id") == "msg_retry_test"
        ).first()
        assert message is not None
    
    async def test_webhook_media_message(self, test_db: Session):
        """Test handling of media messages."""
        message_service = MessageService(test_db)
        agent_service = AgentService(test_db)
        webhook_handler = WebhookHandlerService(test_db, message_service, agent_service)
        
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow(),
            "data": {
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_media_123",
                "text": None,
                "media_url": "https://example.com/image.jpg",
                "media_type": "image",
                "timestamp": datetime.utcnow()
            }
        }
        
        event = WhatsAppWebhookEvent(**event_data)
        
        # Process webhook
        result = await webhook_handler.handle_webhook(event)
        
        assert result["status"] == "stored"  # Not processed (no text)
        assert "message_id" in result
        
        # Verify message was stored with media metadata
        message = test_db.query(Message).filter(
            Message.media_metadata.op("->>")("whatsapp_message_id") == "msg_media_123"
        ).first()
        assert message is not None
        assert message.content is None
        assert message.message_type == "image"
        assert message.media_metadata["media_url"] == "https://example.com/image.jpg"
        assert message.media_metadata["media_type"] == "image"
    
    async def test_webhook_message_status_update(self, test_db: Session):
        """Test updating message status from webhook."""
        # Create a user and message first
        user = User(phone_number="+1234567890", display_name="Test User")
        test_db.add(user)
        test_db.commit()
        
        message = Message(
            user_id=user.id,
            session_id=1,
            sender_jid="service@s.whatsapp.net",
            recipient_jid="+1234567890@s.whatsapp.net",
            message_type="text",
            content="Test message",
            timestamp=datetime.utcnow(),
            media_metadata={"whatsapp_message_id": "msg_status_123"}
        )
        test_db.add(message)
        test_db.commit()
        
        message_service = MessageService(test_db)
        agent_service = AgentService(test_db)
        webhook_handler = WebhookHandlerService(test_db, message_service, agent_service)
        
        # Send status update
        event_data = {
            "event_type": "message.sent",
            "timestamp": datetime.utcnow(),
            "data": {
                "message_id": "msg_status_123",
                "status": "delivered",
                "to_number": "+1234567890@s.whatsapp.net",
                "timestamp": datetime.utcnow()
            }
        }
        
        event = WhatsAppWebhookEvent(**event_data)
        result = await webhook_handler.handle_webhook(event)
        
        assert result["status"] == "updated"
        
        # Verify status was updated
        test_db.refresh(message)
        assert message.media_metadata["status"] == "delivered"
    
    async def test_webhook_concurrent_messages(self, test_db: Session):
        """Test handling multiple concurrent webhook events."""
        message_service = MessageService(test_db)
        agent_service = AgentService(test_db)
        webhook_handler = WebhookHandlerService(test_db, message_service, agent_service)
        
        # Create multiple events
        events = []
        for i in range(5):
            event_data = {
                "event_type": "message.received",
                "timestamp": datetime.utcnow(),
                "data": {
                    "from_number": f"+123456789{i}@s.whatsapp.net",
                    "to_number": "+0987654321@s.whatsapp.net",
                    "message_id": f"msg_concurrent_{i}",
                    "text": f"Message {i}",
                    "timestamp": datetime.utcnow()
                }
            }
            events.append(WhatsAppWebhookEvent(**event_data))
        
        # Mock agent processing
        with patch.object(agent_service, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = None
            
            # Process all events concurrently
            results = await asyncio.gather(*[
                webhook_handler.handle_webhook(event) for event in events
            ])
        
        # Verify all succeeded
        for result in results:
            assert result["status"] == "processed"
        
        # Verify all messages were stored
        for i in range(5):
            message = test_db.query(Message).filter(
                Message.media_metadata.op("->>")("whatsapp_message_id") == f"msg_concurrent_{i}"
            ).first()
            assert message is not None
            assert message.content == f"Message {i}"
        
        # Verify all users were created
        for i in range(5):
            user = test_db.query(User).filter(User.phone_number == f"+123456789{i}").first()
            assert user is not None