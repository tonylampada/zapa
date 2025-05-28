from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


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
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_message_at: Optional[datetime]
    total_messages: int

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserDetailResponse(UserSummary):
    user_metadata: Optional[Dict[str, Any]]
    llm_config_set: bool
    messages_sent: int
    messages_received: int

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+[1-9]\d{1,14}$')
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    user_metadata: Optional[Dict[str, Any]] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    user_metadata: Optional[Dict[str, Any]] = None


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
    messages: List[MessageSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class LLMProviderInfo(BaseModel):
    provider: str
    name: str
    models: List[str]
    supports_function_calling: bool


class LLMConfigResponse(BaseModel):
    id: int
    user_id: int
    provider: str
    model_settings: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMConfigCreate(BaseModel):
    provider: str = Field(..., pattern=r'^(openai|anthropic|google)$')
    api_key: str = Field(..., min_length=1)
    model_settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class LLMConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    model_settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class LLMConfigTestResponse(BaseModel):
    success: bool
    error_message: Optional[str] = None
    response_time_ms: int
    model_used: str


class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_messages: int
    messages_today: int
    average_response_time_ms: float
    llm_provider_usage: Dict[str, int]


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
    download_url: Optional[str] = None
    error_message: Optional[str] = None