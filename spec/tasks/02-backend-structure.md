# Task 02: Backend Structure Implementation with Tests

## Objective
Create the FastAPI backend structure following the plumbing+intelligence architecture pattern, with comprehensive tests for each component.

## Requirements
- Set up FastAPI application with proper configuration
- Create base structure for API routers
- Implement dependency injection setup
- Create base exception handling
- Write tests for all components

## Files to Create

### backend/app/core/config.py
```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./test.db"
    
    # Security
    SECRET_KEY: str = "test-secret-key"
    ADMIN_TOKEN_SECRET: str = "test-admin-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # WhatsApp Bridge
    WHATSAPP_API_URL: str = "http://localhost:3000"
    WHATSAPP_API_KEY: str = "test-api-key"
    
    # OpenAI
    OPENAI_API_KEY: str = "test-openai-key"
    
    # Redis (optional)
    REDIS_URL: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8080"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### backend/tests/test_config.py
```python
import os
import pytest
from app.core.config import Settings

def test_default_settings():
    """Test that settings have sensible defaults."""
    settings = Settings()
    assert settings.DATABASE_URL == "sqlite:///./test.db"
    assert settings.SECRET_KEY == "test-secret-key"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.CORS_ORIGINS == ["http://localhost:8080"]

def test_settings_from_env():
    """Test that settings can be loaded from environment variables."""
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"
    os.environ["SECRET_KEY"] = "env-secret-key"
    
    settings = Settings()
    assert settings.DATABASE_URL == "postgresql://test:test@localhost/test"
    assert settings.SECRET_KEY == "env-secret-key"
    
    # Cleanup
    del os.environ["DATABASE_URL"]
    del os.environ["SECRET_KEY"]
```

### backend/app/core/exceptions.py
```python
from fastapi import HTTPException, status

class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

class BadRequestException(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class ConflictException(HTTPException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
```

### backend/tests/test_exceptions.py
```python
import pytest
from fastapi import status
from app.core.exceptions import (
    NotFoundException, 
    UnauthorizedException,
    BadRequestException,
    ConflictException
)

def test_not_found_exception():
    """Test NotFoundException."""
    exc = NotFoundException("User not found")
    assert exc.status_code == status.HTTP_404_NOT_FOUND
    assert exc.detail == "User not found"

def test_unauthorized_exception():
    """Test UnauthorizedException."""
    exc = UnauthorizedException()
    assert exc.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.detail == "Unauthorized"

def test_bad_request_exception():
    """Test BadRequestException."""
    exc = BadRequestException("Invalid input")
    assert exc.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.detail == "Invalid input"

def test_conflict_exception():
    """Test ConflictException."""
    exc = ConflictException("Resource already exists")
    assert exc.status_code == status.HTTP_409_CONFLICT
    assert exc.detail == "Resource already exists"
```

### backend/app/core/security.py
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
```

### backend/tests/test_security.py
```python
import pytest
from datetime import timedelta
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token
)

def test_password_hashing():
    """Test password hashing and verification."""
    password = "testpassword123"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)

def test_create_and_verify_token():
    """Test JWT token creation and verification."""
    data = {"sub": "testuser", "role": "admin"}
    token = create_access_token(data)
    
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "testuser"
    assert payload["role"] == "admin"
    assert "exp" in payload

def test_verify_invalid_token():
    """Test verification of invalid token."""
    invalid_token = "invalid.token.here"
    payload = verify_token(invalid_token)
    assert payload is None

def test_token_expiration():
    """Test token with custom expiration."""
    data = {"sub": "testuser"}
    # Create token that expires in 1 second
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    
    # Should be expired
    payload = verify_token(token)
    assert payload is None
```

### backend/app/main.py (updated)
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import BadRequestException

app = FastAPI(
    title="WhatsApp Agent API",
    version="0.1.0",
    description="Backend API for WhatsApp Agent System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-agent-backend"}

@app.get("/test-error")
async def test_error():
    """Endpoint to test error handling."""
    raise BadRequestException("This is a test error")
```

### backend/tests/test_main.py
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_cors_headers(client):
    """Test that CORS headers are properly set."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:8080"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_global_exception_handler(client):
    """Test global exception handling."""
    # This would need a special endpoint that raises an unhandled exception
    # For now, we test the custom exception
    response = client.get("/test-error")
    assert response.status_code == 400
    assert response.json()["detail"] == "This is a test error"
```

### Update backend/pyproject.toml
```toml
[project]
name = "whatsapp-agent-backend"
version = "0.1.0"
description = "WhatsApp Agent System Backend"
requires-python = ">=3.10"
dependencies = [
    "fastapi==0.104.1",
    "uvicorn[standard]==0.24.0",
    "pydantic==2.5.2",
    "pydantic-settings==2.1.0",
    "python-jose[cryptography]==3.3.0",
    "passlib[bcrypt]==1.7.4",
    "python-multipart==0.0.6",
]

[tool.uv]
dev-dependencies = [
    "pytest==7.4.3",
    "pytest-asyncio==0.21.1",
    "pytest-cov==4.1.0",
    "httpx==0.25.2",
    "black==23.12.0",
    "ruff==0.1.9",
]
```

## Tests to Verify

1. **Configuration Tests** - Verify settings load correctly from environment
2. **Security Tests** - Test password hashing and JWT token handling
3. **Exception Tests** - Verify custom exceptions work correctly
4. **CORS Tests** - Ensure CORS headers are set properly
5. **Error Handling Tests** - Test global exception handler

## Success Criteria
- [ ] All core modules created with tests
- [ ] Configuration management with environment variables works
- [ ] Security utilities (password hashing, JWT) work correctly
- [ ] Custom exceptions are properly defined
- [ ] All tests pass locally
- [ ] All tests pass in GitHub Actions
- [ ] Code coverage is above 90%

## Commands to Run
```bash
# Run all tests
cd backend
uv run pytest tests -v

# Run specific test file
uv run pytest tests/test_security.py -v

# Run with coverage
uv run pytest tests -v --cov=app --cov-report=term-missing

# Check what lines are not covered
uv run pytest tests -v --cov=app --cov-report=html
# Then open htmlcov/index.html in browser
```