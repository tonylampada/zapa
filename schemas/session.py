from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionType(str, Enum):
    """Session type enum."""

    MAIN = "main"
    USER = "user"


class SessionStatus(str, Enum):
    """Session status enum."""

    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SessionBase(BaseModel):
    """Base session schema."""

    session_type: SessionType = SessionType.MAIN
    status: SessionStatus = SessionStatus.DISCONNECTED
    session_metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreate(SessionBase):
    """Schema for creating a session."""

    user_id: int


class SessionUpdate(BaseModel):
    """Schema for updating a session."""

    status: SessionStatus | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    session_metadata: dict[str, Any] | None = None


class SessionResponse(SessionBase):
    """Schema for session response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    connected_at: datetime | None
    disconnected_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
