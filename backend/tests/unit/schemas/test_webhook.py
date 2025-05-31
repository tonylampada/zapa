"""Unit tests for webhook schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.webhook import (
    WebhookEventType,
    WhatsAppWebhookEvent,
    MessageReceivedData,
    MessageSentData,
    MessageFailedData,
    ConnectionStatusData
)


class TestWebhookSchemas:
    """Test webhook schema validation."""
    
    def test_webhook_event_parsing(self):
        """Test parsing of webhook event."""
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow(),
            "data": {
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "message_id": "msg_123",
                "text": "Hello",
                "timestamp": datetime.utcnow()
            }
        }
        event = WhatsAppWebhookEvent(**event_data)
        assert event.event_type == WebhookEventType.MESSAGE_RECEIVED
        assert isinstance(event.timestamp, datetime)
        assert event.data["from_number"] == "+1234567890"
    
    def test_message_received_data(self):
        """Test MessageReceivedData validation."""
        data = {
            "from_number": "+1234567890@s.whatsapp.net",
            "to_number": "+0987654321@s.whatsapp.net",
            "message_id": "msg_123",
            "text": "Test message",
            "timestamp": datetime.utcnow()
        }
        message_data = MessageReceivedData(**data)
        assert message_data.from_number == "+1234567890@s.whatsapp.net"
        assert message_data.text == "Test message"
        assert message_data.media_url is None
        assert message_data.media_type is None
    
    def test_message_received_with_media(self):
        """Test MessageReceivedData with media."""
        data = {
            "from_number": "+1234567890@s.whatsapp.net",
            "to_number": "+0987654321@s.whatsapp.net",
            "message_id": "msg_123",
            "text": None,
            "media_url": "https://example.com/image.jpg",
            "media_type": "image",
            "timestamp": datetime.utcnow()
        }
        message_data = MessageReceivedData(**data)
        assert message_data.text is None
        assert message_data.media_url == "https://example.com/image.jpg"
        assert message_data.media_type == "image"
    
    def test_message_sent_data(self):
        """Test MessageSentData validation."""
        data = {
            "message_id": "msg_123",
            "to_number": "+1234567890@s.whatsapp.net",
            "timestamp": datetime.utcnow()
        }
        sent_data = MessageSentData(**data)
        assert sent_data.message_id == "msg_123"
        assert sent_data.status == "sent"  # Default value
        assert sent_data.to_number == "+1234567890@s.whatsapp.net"
    
    def test_message_failed_data(self):
        """Test MessageFailedData validation."""
        data = {
            "message_id": "msg_123",
            "error": "Network timeout",
            "to_number": "+1234567890@s.whatsapp.net",
            "timestamp": datetime.utcnow()
        }
        failed_data = MessageFailedData(**data)
        assert failed_data.message_id == "msg_123"
        assert failed_data.error == "Network timeout"
    
    def test_connection_status_data(self):
        """Test ConnectionStatusData validation."""
        data = {
            "status": "connected",
            "session_id": "session_123",
            "timestamp": datetime.utcnow()
        }
        status_data = ConnectionStatusData(**data)
        assert status_data.status == "connected"
        assert status_data.session_id == "session_123"
    
    def test_invalid_event_type(self):
        """Test invalid event type raises error."""
        with pytest.raises(ValidationError):
            WhatsAppWebhookEvent(
                event_type="invalid.event",
                timestamp=datetime.utcnow(),
                data={}
            )
    
    def test_missing_required_fields(self):
        """Test missing required fields raise errors."""
        # Missing from_number
        with pytest.raises(ValidationError):
            MessageReceivedData(
                to_number="+1234567890",
                message_id="msg_123",
                timestamp=datetime.utcnow()
            )
        
        # Missing message_id
        with pytest.raises(ValidationError):
            MessageSentData(
                to_number="+1234567890",
                timestamp=datetime.utcnow()
            )