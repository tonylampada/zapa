# Task 10: Admin API Endpoints

**Dependencies**: Task 09 (Agent Service with LLM Tools)
**Estimated Time**: 2-3 hours
**CI Required**: ✅ All tests must pass

## Objective

Create the admin API endpoints for the Zapa Private service that allow administrators to manage users, view conversation history, configure LLM settings, and monitor system health. These endpoints will be used by the Vue.js admin frontend.

## Requirements

### User Management Endpoints
- List all users with pagination
- View user details and statistics
- Create/update/delete users
- View user's conversation history

### LLM Configuration Endpoints
- Get/set user's LLM provider configuration
- Test LLM configuration validity
- List available LLM providers and models

### System Management Endpoints
- Health check and system status
- View system-wide statistics
- Export conversation data
- Clear user conversation history

### Security
- JWT-based authentication for all endpoints
- Role-based access control (admin only)
- Input validation and sanitization
- Rate limiting on sensitive endpoints

## Test Strategy

### Unit Tests (Always Run)
- API endpoint logic with mocked dependencies
- Authentication and authorization logic
- Input validation and error handling
- Response formatting

### Integration Tests (Skippable)
- Full API endpoint testing with real database
- Authentication flow testing
- Performance testing with large datasets

## Files to Create

### API Routers
```
backend/zapa_private/app/api/admin/users.py
backend/zapa_private/app/api/admin/llm_config.py
backend/zapa_private/app/api/admin/system.py
```

### Authentication
```
backend/zapa_private/app/api/auth.py
backend/zapa_private/app/core/security.py
```

### Schemas
```
backend/shared/app/schemas/admin_schemas.py
```

### Tests
```
backend/zapa_private/tests/api/test_admin_users.py
backend/zapa_private/tests/api/test_admin_llm_config.py
backend/zapa_private/tests/api/test_admin_system.py
backend/zapa_private/tests/api/test_auth.py
```

## Implementation Details

### User Management Endpoints

```python
# backend/zapa_private/app/api/admin/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_admin
from app.services.message_service import MessageService
from shared.app.schemas.admin_schemas import (
    UserListResponse, UserDetailResponse, UserCreate, UserUpdate,
    ConversationHistoryResponse, PaginationParams
)
from shared.app.models.models import User

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """List all users with pagination and optional search."""
    # Implementation for listing users
    pass


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get detailed information about a specific user."""
    pass


@router.post("/", response_model=UserDetailResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Create a new user."""
    pass


@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Update an existing user."""
    pass


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Delete a user and all their data."""
    pass


@router.get("/{user_id}/conversations", response_model=ConversationHistoryResponse)
async def get_user_conversations(
    user_id: int,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get conversation history for a specific user."""
    pass


@router.delete("/{user_id}/conversations")
async def clear_user_conversations(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Clear all conversation history for a user."""
    pass
```

### LLM Configuration Endpoints

```python
# backend/zapa_private/app/api/admin/llm_config.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_admin
from app.adapters.llm_adapter_factory import LLMAdapterFactory
from shared.app.schemas.admin_schemas import (
    LLMConfigResponse, LLMConfigCreate, LLMConfigUpdate,
    LLMProviderInfo, LLMConfigTestResponse
)

router = APIRouter(prefix="/admin/llm-config", tags=["admin-llm"])


@router.get("/providers", response_model=List[LLMProviderInfo])
async def get_available_providers(
    current_admin = Depends(get_current_admin)
):
    """Get list of available LLM providers and their models."""
    return [
        {
            "provider": "openai",
            "name": "OpenAI",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "supports_function_calling": True
        },
        {
            "provider": "anthropic",
            "name": "Anthropic",
            "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "supports_function_calling": True
        },
        {
            "provider": "google",
            "name": "Google",
            "models": ["gemini-pro", "gemini-pro-vision"],
            "supports_function_calling": True
        }
    ]


@router.get("/{user_id}", response_model=LLMConfigResponse)
async def get_user_llm_config(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get LLM configuration for a user."""
    pass


@router.post("/{user_id}", response_model=LLMConfigResponse)
async def create_user_llm_config(
    user_id: int,
    config_data: LLMConfigCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Create LLM configuration for a user."""
    pass


@router.put("/{user_id}", response_model=LLMConfigResponse)
async def update_user_llm_config(
    user_id: int,
    config_data: LLMConfigUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Update LLM configuration for a user."""
    pass


@router.post("/{user_id}/test", response_model=LLMConfigTestResponse)
async def test_user_llm_config(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Test if the user's LLM configuration is working."""
    pass
```

### System Management Endpoints

```python
# backend/zapa_private/app/api/admin/system.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_admin
from shared.app.schemas.admin_schemas import (
    SystemStatsResponse, SystemHealthResponse, ExportDataResponse
)

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get system health status."""
    # Check database connectivity, memory usage, etc.
    pass


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get system-wide statistics."""
    pass


@router.post("/export")
async def export_system_data(
    start_date: datetime,
    end_date: datetime,
    include_messages: bool = True,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Export system data for backup or analysis."""
    pass
```

### Authentication and Security

```python
# backend/zapa_private/app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from shared.app.models.models import User

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.ADMIN_TOKEN_SECRET, algorithm="HS256")
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.ADMIN_TOKEN_SECRET, algorithms=["HS256"])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)):
    """Ensure current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
```

### Admin Schemas

```python
# backend/shared/app/schemas/admin_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class UserSummary(BaseModel):
    id: int
    phone_number: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_message_at: Optional[datetime]
    total_messages: int

class UserListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int

class UserDetailResponse(UserSummary):
    metadata: Optional[Dict[str, Any]]
    llm_config_set: bool
    messages_sent: int
    messages_received: int

class UserCreate(BaseModel):
    phone_number: str = Field(..., regex=r'^\+[1-9]\d{1,14}$')
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

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

class LLMConfigCreate(BaseModel):
    provider: str = Field(..., regex=r'^(openai|anthropic|google)$')
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
```

## Acceptance Criteria

### API Functionality
- [ ] All user management endpoints work correctly
- [ ] LLM configuration endpoints handle all providers
- [ ] System endpoints provide accurate health and stats
- [ ] Authentication is required for all admin endpoints

### Security
- [ ] JWT authentication works correctly
- [ ] Admin role checking prevents unauthorized access
- [ ] Input validation prevents injection attacks
- [ ] API keys are properly encrypted in database

### Data Handling
- [ ] Pagination works correctly for large datasets
- [ ] Search functionality filters users appropriately
- [ ] Data export includes all requested information
- [ ] User deletion removes all associated data

### Testing
- [ ] Unit tests cover all endpoint logic
- [ ] Authentication logic is thoroughly tested
- [ ] Integration tests verify database operations
- [ ] Error handling is tested for all edge cases

### Performance
- [ ] List endpoints are fast with large datasets (< 500ms)
- [ ] Authentication checks are efficient
- [ ] Database queries are optimized

## Test Examples

### Unit Test Structure
```python
# backend/zapa_private/tests/api/test_admin_users.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

class TestAdminUsersAPI:
    def test_list_users_success(self, client: TestClient, admin_token):
        response = client.get(
            "/admin/users/",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        # Test response structure
    
    def test_list_users_unauthorized(self, client: TestClient):
        response = client.get("/admin/users/")
        assert response.status_code == 401
    
    def test_create_user_success(self, client: TestClient, admin_token):
        user_data = {
            "phone_number": "+1234567890",
            "first_name": "Test",
            "last_name": "User"
        }
        response = client.post(
            "/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
```

## Next Steps

After completing this task:
1. Verify all tests pass in CI
2. Test API endpoints with Postman/curl
3. Ensure authentication works correctly
4. Move to Task 11: Webhook Handlers for WhatsApp Events

## Notes

- Focus on security - these are admin endpoints with sensitive data
- Ensure proper error handling and user feedback
- Keep response times fast even with large datasets
- Follow REST conventions for endpoint design