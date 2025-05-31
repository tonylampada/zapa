"""Unit tests for webhook handler service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.webhook_handler import WebhookHandlerService
from app.schemas.webhook import (
    WhatsAppWebhookEvent,
    WebhookEventType
)
from app.models import User


@pytest.fixture
def mock_services():
    """Create mock services."""
    class MockServices:
        message = Mock()
        agent = Mock()
        db = Mock()
    
    services = MockServices()
    
    # Set up async mocks
    services.message.store_message = AsyncMock()
    services.message.update_message_status = AsyncMock()
    services.agent.process_message = AsyncMock()
    
    return services


@pytest.mark.asyncio
class TestWebhookHandlerService:
    """Test webhook handler service."""
    
    async def test_handle_message_received(self, mock_services):
        """Test handling of message received event."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        # Mock user lookup
        mock_user = User(id=1, phone_number="+1234567890", display_name="Test User")
        mock_services.db.query.return_value.filter.return_value.first.return_value = mock_user
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_RECEIVED,
            timestamp=datetime.utcnow(),
            data={
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_123",
                "text": "Hello AI",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.store_message.return_value = Mock(id=1)
        mock_services.agent.process_message.return_value = None
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "processed"
        assert result["message_id"] == 1
        mock_services.message.store_message.assert_called_once()
        mock_services.agent.process_message.assert_called_once()
    
    async def test_handle_message_received_new_user(self, mock_services):
        """Test handling message from new user."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        # Mock user not found
        mock_services.db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock commit and refresh
        mock_services.db.add = Mock()
        mock_services.db.commit = Mock()
        mock_services.db.refresh = Mock()
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_RECEIVED,
            timestamp=datetime.utcnow(),
            data={
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_123",
                "text": "Hello",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.store_message.return_value = Mock(id=1)
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "processed"
        mock_services.db.add.assert_called_once()
        mock_services.db.commit.assert_called_once()
    
    async def test_handle_message_received_with_media(self, mock_services):
        """Test handling message with media."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        mock_user = User(id=1, phone_number="+1234567890", display_name="Test User")
        mock_services.db.query.return_value.filter.return_value.first.return_value = mock_user
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_RECEIVED,
            timestamp=datetime.utcnow(),
            data={
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_123",
                "text": None,
                "media_url": "https://example.com/image.jpg",
                "media_type": "image",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.store_message.return_value = Mock(id=1)
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "stored"  # No text, so not processed
        assert result["message_id"] == 1
        mock_services.agent.process_message.assert_not_called()
    
    async def test_handle_message_sent(self, mock_services):
        """Test handling of message sent confirmation."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_SENT,
            timestamp=datetime.utcnow(),
            data={
                "message_id": "msg_123",
                "status": "delivered",
                "to_number": "+1234567890@s.whatsapp.net",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.update_message_status.return_value = Mock(id=1)
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "updated"
        assert result["message_id"] == "msg_123"
        mock_services.message.update_message_status.assert_called_once_with(
            whatsapp_message_id="msg_123",
            status="delivered"
        )
    
    async def test_handle_message_failed(self, mock_services):
        """Test handling of failed message."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_FAILED,
            timestamp=datetime.utcnow(),
            data={
                "message_id": "msg_123",
                "error": "Network timeout",
                "to_number": "+1234567890@s.whatsapp.net",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.update_message_status.return_value = Mock(id=1)
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "updated"
        assert result["error"] == "Network timeout"
        mock_services.message.update_message_status.assert_called_once_with(
            whatsapp_message_id="msg_123",
            status="failed: Network timeout"
        )
    
    async def test_handle_connection_status(self, mock_services):
        """Test handling of connection status update."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.CONNECTION_STATUS,
            timestamp=datetime.utcnow(),
            data={
                "status": "connected",
                "session_id": "session_123",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "acknowledged"
        assert result["connection_status"] == "connected"
        assert result["session_id"] == "session_123"
    
    async def test_handle_unknown_event_type(self, mock_services):
        """Test handling of unknown event type."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        # Create event with mock event type
        event = Mock(spec=WhatsAppWebhookEvent)
        event.event_type = "unknown.event"
        
        result = await handler.handle_webhook(event)
        
        assert result["status"] == "ignored"
        assert result["reason"] == "unknown_event_type"
    
    async def test_agent_processing_failure(self, mock_services):
        """Test handling when agent processing fails."""
        handler = WebhookHandlerService(
            db=mock_services.db,
            message_service=mock_services.message,
            agent_service=mock_services.agent
        )
        
        mock_user = User(id=1, phone_number="+1234567890", display_name="Test User")
        mock_services.db.query.return_value.filter.return_value.first.return_value = mock_user
        
        event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_RECEIVED,
            timestamp=datetime.utcnow(),
            data={
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_123",
                "text": "Hello",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_services.message.store_message.return_value = Mock(id=1)
        
        # Mock agent failure after retries
        mock_services.agent.process_message.side_effect = Exception("Processing failed")
        
        # Patch RetryHandler to fail immediately
        with patch('app.services.webhook_handler.RetryHandler.with_retry') as mock_retry:
            mock_retry.side_effect = Exception("Processing failed")
            
            result = await handler.handle_webhook(event)
            
            assert result["status"] == "stored"
            assert result["message_id"] == 1
            assert result["processing"] == "failed"