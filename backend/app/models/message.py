import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .session import Session
    from .user import User


class MessageType(str, enum.Enum):
    """Type of WhatsApp message."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class Message(Base):
    """WhatsApp message model."""

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True  # Redundant for performance
    )
    sender_jid: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    recipient_jid: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)  # Nullable for media messages
    caption: Mapped[str | None] = mapped_column(Text)
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("message.id"), index=True
    )
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")
    reply_to: Mapped[Optional["Message"]] = relationship(
        remote_side=[id], foreign_keys=[reply_to_id]
    )
