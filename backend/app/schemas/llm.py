from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMProvider(str, Enum):
    """LLM provider enum."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMConfigBase(BaseModel):
    """Base LLM config schema."""

    model_config = ConfigDict(protected_namespaces=())

    provider: LLMProvider
    model_settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class LLMConfigCreate(LLMConfigBase):
    """Schema for creating LLM config."""

    api_key: str = Field(..., min_length=1)  # Will be encrypted before storage


class LLMConfigUpdate(BaseModel):
    """Schema for updating LLM config."""

    api_key: str | None = Field(None, min_length=1)
    model_settings: dict[str, Any] | None = None
    is_active: bool | None = None


class LLMConfigRequest(LLMConfigBase):
    """Schema for LLM config request (create/update)."""

    api_key: str = Field(..., min_length=1)  # Will be encrypted before storage


class LLMConfigResponse(LLMConfigBase):
    """Schema for LLM config response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    # Note: api_key_encrypted is never returned in API responses
    created_at: datetime
    updated_at: datetime | None


class LLMTestResponse(BaseModel):
    """Schema for LLM configuration test response."""

    success: bool
    message: str
    response_time_ms: int | None = None
    provider: str | None = None
    model: str | None = None
