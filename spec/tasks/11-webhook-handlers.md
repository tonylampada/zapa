# Task 11: Webhook Handlers for WhatsApp Events

## Overview
Create webhook handlers in Zapa Private to receive and process WhatsApp events from the Bridge service. This establishes the incoming message flow from WhatsApp users.

## Prerequisites
- Task 06: WhatsApp Bridge Adapter (for sending messages)
- Task 08: Message Service (for storing messages)
- Task 09: Agent Service (for processing messages)

## Acceptance Criteria
1. POST /webhooks/whatsapp endpoint accepts Bridge events
2. Handles message.received events
3. Handles message.sent confirmations
4. Handles connection status updates
5. Validates webhook payloads
6. Stores messages in database
7. Triggers agent processing for user messages
8. Handles errors gracefully with retries

## Test-Driven Development Steps

### Step 1: Create Webhook Models
```python
# backend/app/schemas/webhook.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class WebhookEventType(str, Enum):
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_FAILED = "message.failed"
    CONNECTION_STATUS = "connection.status"

class WhatsAppWebhookEvent(BaseModel):
    event_type: WebhookEventType
    timestamp: datetime
    data: Dict[str, Any]
    
class MessageReceivedData(BaseModel):
    from_number: str
    to_number: str
    message_id: str
    text: Optional[str]
    media_url: Optional[str]
    media_type: Optional[str]
    timestamp: datetime
```

**Tests:**
```python
# backend/tests/unit/schemas/test_webhook.py
def test_webhook_event_parsing():
    event_data = {
        "event_type": "message.received",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "message_id": "msg_123",
            "text": "Hello",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }
    event = WhatsAppWebhookEvent(**event_data)
    assert event.event_type == WebhookEventType.MESSAGE_RECEIVED
```

### Step 2: Create Webhook Handler Service
```python
# backend/app/services/webhook_handler.py
from typing import Dict, Any
import logging
from app.schemas.webhook import (
    WhatsAppWebhookEvent, 
    WebhookEventType,
    MessageReceivedData
)
from app.services.message_service import MessageService
from app.services.agent_service import AgentService
from app.models import MessageType

logger = logging.getLogger(__name__)

class WebhookHandlerService:
    def __init__(
        self,
        message_service: MessageService,
        agent_service: AgentService
    ):
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
        """Handle incoming message from user."""
        data = MessageReceivedData(**event.data)
        
        # Store the message
        message = await self.message_service.store_message(
            from_number=data.from_number,
            to_number=data.to_number,
            content=data.text,
            direction=MessageDirection.INBOUND,
            whatsapp_message_id=data.message_id,
            media_url=data.media_url,
            media_type=data.media_type
        )
        
        # Trigger agent processing
        try:
            await self.agent_service.process_message(
                user_phone=data.from_number,
                message_content=data.text
            )
            return {"status": "processed", "message_id": message.id}
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            # Return success anyway - we stored the message
            return {"status": "stored", "message_id": message.id, "processing": "failed"}
```

**Tests:**
```python
# backend/tests/unit/services/test_webhook_handler.py
@pytest.mark.asyncio
async def test_handle_message_received(mock_services):
    handler = WebhookHandlerService(
        message_service=mock_services.message,
        agent_service=mock_services.agent
    )
    
    event = WhatsAppWebhookEvent(
        event_type=WebhookEventType.MESSAGE_RECEIVED,
        timestamp=datetime.utcnow(),
        data={
            "from_number": "+1234567890",
            "to_number": "+0987654321",
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
```

### Step 3: Create Webhook API Endpoint
```python
# backend/app/private/api/v1/webhooks.py
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from app.schemas.webhook import WhatsAppWebhookEvent
from app.services.webhook_handler import WebhookHandlerService
from app.core.dependencies import get_webhook_handler

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/whatsapp")
async def whatsapp_webhook(
    event: WhatsAppWebhookEvent,
    webhook_handler: WebhookHandlerService = Depends(get_webhook_handler),
    x_webhook_signature: Optional[str] = Header(None)
):
    """
    Receive webhook events from WhatsApp Bridge.
    
    Note: In production, validate x_webhook_signature for security.
    """
    try:
        result = await webhook_handler.handle_webhook(event)
        return result
    except Exception as e:
        # Log but don't fail - webhook delivery is critical
        import logging
        logging.error(f"Webhook processing error: {e}")
        return {"status": "error", "message": str(e)}
```

**Tests:**
```python
# backend/tests/integration/private/api/v1/test_webhook_endpoints.py
@pytest.mark.asyncio
async def test_webhook_endpoint(test_client, test_db):
    event_data = {
        "event_type": "message.received",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "message_id": "msg_123",
            "text": "Test message",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    response = await test_client.post(
        "/webhooks/whatsapp",
        json=event_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["processed", "stored"]
```

### Step 4: Add Connection Status Handling
```python
# Add to webhook_handler.py
async def _handle_connection_status(
    self, 
    event: WhatsAppWebhookEvent
) -> Dict[str, Any]:
    """Handle WhatsApp connection status updates."""
    status = event.data.get("status")
    session_id = event.data.get("session_id")
    
    logger.info(f"WhatsApp connection status: {status} (session: {session_id})")
    
    # Could store in Redis or database for monitoring
    # For now, just log and acknowledge
    return {
        "status": "acknowledged",
        "connection_status": status,
        "session_id": session_id
    }

async def _handle_message_sent(
    self, 
    event: WhatsAppWebhookEvent
) -> Dict[str, Any]:
    """Handle confirmation of sent message."""
    whatsapp_id = event.data.get("message_id")
    status = event.data.get("status", "sent")
    
    # Update message status in database
    await self.message_service.update_message_status(
        whatsapp_message_id=whatsapp_id,
        status=status
    )
    
    return {"status": "updated", "message_id": whatsapp_id}
```

### Step 5: Add Retry Logic for Failed Processing
```python
# backend/app/services/retry_handler.py
from typing import Callable, Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class RetryHandler:
    @staticmethod
    async def with_retry(
        func: Callable,
        *args,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry."""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed: {e}")
        
        raise last_exception

# Update webhook handler to use retry
async def _handle_message_received(self, event: WhatsAppWebhookEvent) -> Dict[str, Any]:
    data = MessageReceivedData(**event.data)
    
    # Store message (critical - no retry)
    message = await self.message_service.store_message(...)
    
    # Process with agent (non-critical - retry)
    try:
        await RetryHandler.with_retry(
            self.agent_service.process_message,
            user_phone=data.from_number,
            message_content=data.text,
            max_retries=3
        )
        return {"status": "processed", "message_id": message.id}
    except Exception as e:
        logger.error(f"Agent processing failed after retries: {e}")
        return {"status": "stored", "message_id": message.id, "processing": "failed"}
```

### Step 6: Add Webhook Validation
```python
# backend/app/core/webhook_security.py
import hmac
import hashlib
from typing import Optional

class WebhookValidator:
    def __init__(self, webhook_secret: Optional[str] = None):
        self.webhook_secret = webhook_secret
    
    def validate_signature(
        self, 
        payload: bytes, 
        signature: Optional[str]
    ) -> bool:
        """Validate webhook signature if secret is configured."""
        if not self.webhook_secret:
            # No validation if secret not configured
            return True
            
        if not signature:
            return False
            
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)

# Update webhook endpoint to validate
@router.post("/whatsapp")
async def whatsapp_webhook(
    event: WhatsAppWebhookEvent,
    request: Request,
    webhook_handler: WebhookHandlerService = Depends(get_webhook_handler),
    x_webhook_signature: Optional[str] = Header(None)
):
    # Validate signature if configured
    validator = WebhookValidator(settings.WEBHOOK_SECRET)
    body = await request.body()
    
    if not validator.validate_signature(body, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook...
```

## Integration Tests

```python
# backend/tests/integration/services/test_webhook_integration.py
import pytest
import asyncio
from datetime import datetime

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_webhook_flow(test_client, test_db, redis_client):
    """Test complete webhook processing flow."""
    # Send webhook event
    event_data = {
        "event_type": "message.received",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "message_id": "msg_test_123",
            "text": "Hello, can you help me?",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    response = await test_client.post(
        "/webhooks/whatsapp",
        json=event_data
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] in ["processed", "stored"]
    
    # Verify message was stored
    # This would query the test database
    # message = await get_message_by_whatsapp_id("msg_test_123")
    # assert message is not None
    # assert message.content == "Hello, can you help me?"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_retry_on_failure(test_client, monkeypatch):
    """Test retry logic when agent processing fails."""
    call_count = 0
    
    async def failing_process_message(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return None
    
    # Monkeypatch agent service to fail twice then succeed
    # Implementation depends on dependency injection setup
    
    event_data = {
        "event_type": "message.received",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "message_id": "msg_retry_test",
            "text": "Test retry",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    response = await test_client.post(
        "/webhooks/whatsapp",
        json=event_data
    )
    
    assert response.status_code == 200
    assert call_count == 3  # Failed twice, succeeded on third
```

## Implementation Notes

1. **Error Handling**: Webhook endpoints should NEVER return 5xx errors as this causes webhook delivery retries from the Bridge
2. **Idempotency**: Design for duplicate webhook deliveries - use message_id to prevent duplicates
3. **Async Processing**: Store message immediately, process with agent asynchronously
4. **Monitoring**: Log all webhook events for debugging and monitoring
5. **Security**: In production, implement webhook signature validation
6. **Performance**: Keep webhook handlers fast - offload heavy processing

## Dependencies
- WhatsApp Bridge Adapter (for response sending)
- Message Service (for storage)
- Agent Service (for AI processing)
- FastAPI for webhook endpoints
- Pydantic for request validation

## Next Steps
- Task 12: Public Service Authentication Flow
- Task 13: WhatsApp Bridge Integration (complete the loop)