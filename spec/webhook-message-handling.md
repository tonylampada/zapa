# Webhook Message Handling Documentation

## Overview

The Zapa webhook system receives events from the WhatsApp Bridge service at the `/api/v1/webhooks/whatsapp` endpoint. This document details how different types of messages are processed, with a focus on user messages versus system messages.

## Webhook Event Types

The webhook handler processes four main event types:

1. **message.received** - Incoming messages from WhatsApp users
2. **message.sent** - Delivery confirmations for outbound messages
3. **message.failed** - Failed message notifications
4. **connection.status** - WhatsApp connection status updates

## Message Processing Flow

### 1. User Messages (From WhatsApp Users)

When a WhatsApp user sends a message to the service number, the following happens:

```json
{
  "event_type": "message.received",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "from_number": "+1234567890@s.whatsapp.net",
    "to_number": "+0987654321@s.whatsapp.net",
    "message_id": "msg_123",
    "text": "Hello, can you help me?",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Processing Steps:**

1. **User Creation/Lookup**
   - Extract phone number from WhatsApp JID (e.g., `+1234567890@s.whatsapp.net` → `+1234567890`)
   - Check if user exists in database
   - If new user: Create user with default display name (e.g., "User 7890")
   - If existing user: Load user record

2. **Message Storage**
   - Determine message type (text, image, audio, video, document)
   - Create message metadata including WhatsApp message ID
   - Store message with:
     - `direction`: "incoming"
     - `content`: Message text (empty string for media messages)
     - `message_type`: Appropriate type based on content
     - `metadata`: WhatsApp-specific data and timestamps

3. **Agent Processing** (Text Messages Only)
   - If message contains text, trigger AI agent processing
   - Agent processing uses retry logic (3 attempts with exponential backoff)
   - Load user's LLM configuration
   - Build conversation context from message history
   - Generate and store AI response
   - Send response back via WhatsApp Bridge

**Response Example:**
```json
{
  "status": "processed",
  "message_id": 123
}
```

### 2. System Messages (From WhatsApp Bridge)

System messages are notifications about message delivery status:

#### Message Sent Confirmation
```json
{
  "event_type": "message.sent",
  "timestamp": "2024-01-15T10:31:00Z",
  "data": {
    "message_id": "msg_sent_123",
    "status": "delivered",
    "to_number": "+1234567890@s.whatsapp.net",
    "timestamp": "2024-01-15T10:31:00Z"
  }
}
```

**Processing:**
- Find message by WhatsApp message ID
- Update message metadata with delivery status
- Log confirmation

**Response:**
```json
{
  "status": "updated",
  "message_id": "msg_sent_123"
}
```

#### Message Failed Notification
```json
{
  "event_type": "message.failed",
  "timestamp": "2024-01-15T10:31:00Z",
  "data": {
    "message_id": "msg_fail_123",
    "error": "Network timeout",
    "to_number": "+1234567890@s.whatsapp.net",
    "timestamp": "2024-01-15T10:31:00Z"
  }
}
```

**Processing:**
- Find message by WhatsApp message ID
- Update status to include failure reason
- Log error for monitoring

**Response:**
```json
{
  "status": "updated",
  "message_id": "msg_fail_123",
  "error": "Network timeout"
}
```

#### Connection Status Update
```json
{
  "event_type": "connection.status",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "status": "connected",
    "session_id": "session_123",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Processing:**
- Log connection status change
- Could be stored in Redis/database for monitoring
- Currently just acknowledged

**Response:**
```json
{
  "status": "acknowledged",
  "connection_status": "connected",
  "session_id": "session_123"
}
```

## Key Differences: User vs System Messages

| Aspect | User Messages | System Messages |
|--------|--------------|-----------------|
| **Event Type** | message.received | message.sent, message.failed, connection.status |
| **Direction** | Incoming (from user) | Internal (from bridge) |
| **User Creation** | Creates new users if needed | Never creates users |
| **Message Storage** | Always stores in database | Updates existing messages |
| **Agent Processing** | Triggered for text messages | Never triggered |
| **Retry Logic** | Yes (for agent processing) | No |
| **Response Time** | Can be slow (AI processing) | Always fast |
| **Critical Path** | Message storage is critical | Status updates are non-critical |

## Media Message Handling

When users send media (images, audio, video, documents):

```json
{
  "event_type": "message.received",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "from_number": "+1234567890@s.whatsapp.net",
    "to_number": "+0987654321@s.whatsapp.net",
    "message_id": "msg_media_123",
    "text": null,
    "media_url": "https://example.com/image.jpg",
    "media_type": "image",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Special Handling:**
- Content stored as empty string (schema requirement)
- Media URL and type saved in metadata
- No agent processing (AI only handles text)
- Message type set based on media_type field

## Error Handling

### Webhook Level
- All webhooks return 200 OK to prevent Bridge retries
- Errors logged but wrapped in successful response
- Critical operations (message storage) never use retry
- Non-critical operations (agent processing) use retry with backoff

### Processing Errors
```json
{
  "status": "stored",
  "message_id": 123,
  "processing": "failed"
}
```

This indicates:
- Message was successfully stored (critical path succeeded)
- Agent processing failed (non-critical path failed)
- User won't receive AI response but message is preserved

## Security

### Webhook Signature Validation
- Optional HMAC-SHA256 signature validation
- Configured via `WEBHOOK_SECRET` environment variable
- Uses constant-time comparison to prevent timing attacks
- Header: `X-Webhook-Signature`

### Network Security
- Webhooks only accessible on private network
- No authentication required (secured at network level)
- WhatsApp Bridge trusted as internal service

## Performance Considerations

1. **Fast Response Required**
   - Webhook must respond quickly to avoid timeouts
   - Heavy processing (AI) done asynchronously

2. **Retry Strategy**
   - Message storage: No retry (must succeed)
   - Agent processing: 3 retries with exponential backoff
   - Initial delay: 1 second
   - Backoff multiplier: 2x

3. **Concurrent Processing**
   - Each webhook request processed independently
   - No queuing at webhook level
   - Database handles concurrent message storage

## Monitoring and Debugging

### Success Metrics
- `status: "processed"` - Full success (message stored + AI responded)
- `status: "stored"` - Partial success (message stored, no AI response)
- `status: "updated"` - System message processed
- `status: "acknowledged"` - Connection status noted

### Error States
- `status: "error"` - Webhook processing failed
- `status: "not_found"` - Message not found for update
- `processing: "failed"` - Agent processing failed

### Logging
All webhook events are logged with:
- Event type
- Processing result
- Error details (if any)
- Timing information

## Implementation Details

### Key Files
- `/backend/app/schemas/webhook.py` - Event data models
- `/backend/app/services/webhook_handler.py` - Processing logic
- `/backend/app/private/api/v1/webhooks.py` - API endpoint
- `/backend/app/services/retry_handler.py` - Retry logic
- `/backend/app/core/webhook_security.py` - Signature validation

### Database Impact
- Creates users automatically
- Creates sessions automatically
- Stores all messages (including media metadata)
- Updates message delivery status

### Dependencies
- MessageService - For message storage
- AgentService - For AI processing
- User model - For user management
- SQLAlchemy - For database operations