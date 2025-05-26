from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .auth_code import AuthCode
    from .llm_config import LLMConfig
    from .message import Message
    from .session import Session


class User(Base):
    """User model representing WhatsApp users."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    auth_codes: Mapped[list["AuthCode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    llm_configs: Mapped[list["LLMConfig"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
