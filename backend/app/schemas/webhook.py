from pydantic import BaseModel, Field
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
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: datetime


class MessageSentData(BaseModel):
    message_id: str
    status: str = "sent"
    to_number: str
    timestamp: datetime


class MessageFailedData(BaseModel):
    message_id: str
    error: str
    to_number: str
    timestamp: datetime


class ConnectionStatusData(BaseModel):
    status: str
    session_id: str
    timestamp: datetime
