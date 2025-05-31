"""Integration tests for webhook endpoints."""

import pytest
from datetime import datetime
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.models import User, Message
from app.schemas.message import MessageDirection


@pytest.mark.integration
@pytest.mark.asyncio
class TestWebhookEndpoints:
    """Test webhook API endpoints."""
    
    async def test_webhook_endpoint_message_received(self, test_client: AsyncClient, test_db):
        """Test webhook endpoint for message received event."""
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_123",
                "text": "Test message",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Mock agent service to avoid actual processing
        with patch('app.services.webhook_handler.AgentService.process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = None
            
            response = await test_client.post(
                "/api/v1/webhooks/whatsapp",
                json=event_data
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["processed", "stored"]
        assert "message_id" in data
        
        # Verify message was stored in database
        message = test_db.query(Message).filter(
            Message.media_metadata.op("->>")("whatsapp_message_id") == "msg_123"
        ).first()
        assert message is not None
        assert message.content == "Test message"
        
        # Verify user was created
        user = test_db.query(User).filter(User.phone_number == "+1234567890").first()
        assert user is not None
    
    async def test_webhook_endpoint_message_sent(self, test_client: AsyncClient, test_db):
        """Test webhook endpoint for message sent confirmation."""
        # Create a test message first
        user = User(phone_number="+1234567890", display_name="Test User")
        test_db.add(user)
        test_db.commit()
        
        message = Message(
            user_id=user.id,
            session_id=1,
            sender_jid="service@s.whatsapp.net",
            recipient_jid="+1234567890@s.whatsapp.net",
            message_type="text",
            content="Test",
            timestamp=datetime.utcnow(),
            media_metadata={"whatsapp_message_id": "msg_sent_123"}
        )
        test_db.add(message)
        test_db.commit()
        
        event_data = {
            "event_type": "message.sent",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "message_id": "msg_sent_123",
                "status": "delivered",
                "to_number": "+1234567890@s.whatsapp.net",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        response = await test_client.post(
            "/api/v1/webhooks/whatsapp",
            json=event_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["message_id"] == "msg_sent_123"
        
        # Verify status was updated
        test_db.refresh(message)
        assert message.media_metadata["status"] == "delivered"
    
    async def test_webhook_endpoint_message_failed(self, test_client: AsyncClient, test_db):
        """Test webhook endpoint for failed message."""
        # Create a test message
        user = User(phone_number="+1234567890", display_name="Test User")
        test_db.add(user)
        test_db.commit()
        
        message = Message(
            user_id=user.id,
            session_id=1,
            sender_jid="service@s.whatsapp.net",
            recipient_jid="+1234567890@s.whatsapp.net",
            message_type="text",
            content="Test",
            timestamp=datetime.utcnow(),
            media_metadata={"whatsapp_message_id": "msg_fail_123"}
        )
        test_db.add(message)
        test_db.commit()
        
        event_data = {
            "event_type": "message.failed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "message_id": "msg_fail_123",
                "error": "Network timeout",
                "to_number": "+1234567890@s.whatsapp.net",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        response = await test_client.post(
            "/api/v1/webhooks/whatsapp",
            json=event_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["error"] == "Network timeout"
    
    async def test_webhook_endpoint_connection_status(self, test_client: AsyncClient):
        """Test webhook endpoint for connection status update."""
        event_data = {
            "event_type": "connection.status",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "status": "connected",
                "session_id": "session_123",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        response = await test_client.post(
            "/api/v1/webhooks/whatsapp",
            json=event_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert data["connection_status"] == "connected"
        assert data["session_id"] == "session_123"
    
    async def test_webhook_health_check(self, test_client: AsyncClient):
        """Test webhook health check endpoint."""
        response = await test_client.get("/api/v1/webhooks/whatsapp/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "webhook_handler"
    
    async def test_webhook_invalid_event_type(self, test_client: AsyncClient):
        """Test webhook with invalid event type."""
        event_data = {
            "event_type": "invalid.event",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {}
        }
        
        response = await test_client.post(
            "/api/v1/webhooks/whatsapp",
            json=event_data
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_webhook_signature_validation(self, test_client: AsyncClient):
        """Test webhook signature validation when configured."""
        import hmac
        import hashlib
        import json
        
        # Mock settings to include webhook secret
        with patch('app.core.config.get_settings') as mock_settings:
            mock_settings.return_value.WEBHOOK_SECRET = "test_secret"
            
            event_data = {
                "event_type": "connection.status",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "status": "connected",
                    "session_id": "session_123",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Test with invalid signature
            response = await test_client.post(
                "/api/v1/webhooks/whatsapp",
                json=event_data,
                headers={"X-Webhook-Signature": "invalid_signature"}
            )
            
            assert response.status_code == 401
            assert "Invalid webhook signature" in response.json()["detail"]
    
    async def test_webhook_error_handling(self, test_client: AsyncClient):
        """Test webhook error handling doesn't fail the request."""
        event_data = {
            "event_type": "message.received",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+0987654321@s.whatsapp.net",
                "message_id": "msg_error",
                "text": "Test error",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Mock to raise an exception
        with patch('app.services.webhook_handler.WebhookHandlerService.handle_webhook') as mock_handle:
            mock_handle.side_effect = Exception("Unexpected error")
            
            response = await test_client.post(
                "/api/v1/webhooks/whatsapp",
                json=event_data
            )
        
        # Should still return 200 with error status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Unexpected error" in data["message"]