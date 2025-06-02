import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class LLMProvider(str, enum.Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMConfig(Base):
    """LLM configuration for a user."""

    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)  # Encrypted API key
    model_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict  # model, temperature, max_tokens, etc.
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="llm_configs")
