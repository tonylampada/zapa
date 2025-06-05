from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageDirection(str, Enum):
    """Message direction enum."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SYSTEM = "system"


class MessageType(str, Enum):
    """Message type enum."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message delivery status enum."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageBase(BaseModel):
    """Base message schema."""

    sender_jid: str = Field(..., max_length=50)
    recipient_jid: str = Field(..., max_length=50)
    message_type: MessageType
    content: str | None = None
    caption: str | None = None
    reply_to_id: int | None = None
    media_metadata: dict[str, Any] | None = None


class MessageCreate(BaseModel):
    """Schema for creating a message."""

    content: str
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    whatsapp_message_id: str | None = None
    metadata: dict[str, Any] | None = None
    sender_jid: str | None = None  # Optional, for webhook messages
    recipient_jid: str | None = None  # Optional, for webhook messages


class MessageResponse(BaseModel):
    """Schema for message response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str
    direction: MessageDirection
    message_type: MessageType
    whatsapp_message_id: str | None
    metadata: dict[str, Any] | None
    created_at: datetime


class MessageSearchParams(BaseModel):
    """Parameters for message search."""

    query: str
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ConversationStats(BaseModel):
    """Statistics about a user's conversation."""

    total_messages: int
    messages_sent: int
    messages_received: int
    first_message_date: datetime | None
    last_message_date: datetime | None
    average_messages_per_day: float


# Alias for API consistency
MessageStats = ConversationStats
