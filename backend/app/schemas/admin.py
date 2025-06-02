from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AdminLogin(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserSummary(BaseModel):
    id: int
    phone_number: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    created_at: datetime
    last_message_at: datetime | None
    total_messages: int

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: list[UserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserDetailResponse(UserSummary):
    user_metadata: dict[str, Any] | None
    llm_config_set: bool
    messages_sent: int
    messages_received: int

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool = True
    user_metadata: dict[str, Any] | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    user_metadata: dict[str, Any] | None = None


class MessageSummary(BaseModel):
    id: int
    content: str
    is_from_user: bool
    message_type: str
    created_at: datetime
    status: str

    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    messages: list[MessageSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LLMProviderInfo(BaseModel):
    provider: str
    name: str
    models: list[str]
    supports_function_calling: bool


class LLMConfigResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    model_settings: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMConfigCreate(BaseModel):
    provider: str = Field(..., pattern=r"^(openai|anthropic|google)$")
    api_key: str = Field(..., min_length=1)
    model_settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class LLMConfigUpdate(BaseModel):
    api_key: str | None = None
    model_settings: dict[str, Any] | None = None
    is_active: bool | None = None


class LLMConfigTestResponse(BaseModel):
    success: bool
    error_message: str | None = None
    response_time_ms: int
    model_used: str


class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_messages: int
    messages_today: int
    average_response_time_ms: float
    llm_provider_usage: dict[str, int]


class SystemHealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    database_connected: bool
    whatsapp_bridge_connected: bool
    memory_usage_percent: float
    disk_usage_percent: float
    uptime_seconds: int


class ExportDataResponse(BaseModel):
    export_id: str
    status: str  # "pending", "processing", "completed", "failed"
    download_url: str | None = None
    error_message: str | None = None
