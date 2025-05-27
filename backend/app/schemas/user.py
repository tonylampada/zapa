from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """Base user schema."""

    phone_number: str = Field(..., min_length=10, max_length=20)
    display_name: str | None = Field(None, max_length=255)
    preferences: dict[str, Any] = Field(default_factory=dict)


class UserCreate(UserBase):
    """Schema for creating a user."""

    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    display_name: str | None = Field(None, max_length=255)
    preferences: dict[str, Any] | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_seen: datetime
    last_active: datetime | None
    created_at: datetime
    updated_at: datetime | None
