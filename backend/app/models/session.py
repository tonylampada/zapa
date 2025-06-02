import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .message import Message
    from .user import User


class SessionType(str, enum.Enum):
    """Type of WhatsApp session."""

    MAIN = "main"  # Main service number
    USER = "user"  # User's own number (future feature)


class SessionStatus(str, enum.Enum):
    """Status of WhatsApp session."""

    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Session(Base):
    """WhatsApp session model."""

    __tablename__ = "session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    session_type: Mapped[SessionType] = mapped_column(
        Enum(SessionType), nullable=False, default=SessionType.MAIN
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.DISCONNECTED
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
