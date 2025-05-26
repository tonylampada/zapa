from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    """Message type enum."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class MessageBase(BaseModel):
    """Base message schema."""

    sender_jid: str = Field(..., max_length=50)
    recipient_jid: str = Field(..., max_length=50)
    message_type: MessageType
    content: str | None = None
    caption: str | None = None
    reply_to_id: int | None = None
    media_metadata: dict[str, Any] | None = None


class MessageCreate(MessageBase):
    """Schema for creating a message."""

    session_id: int
    user_id: int
    timestamp: datetime


class MessageResponse(MessageBase):
    """Schema for message response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    user_id: int
    timestamp: datetime
    created_at: datetime
