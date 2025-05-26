# Task 05: Private Service Structure and Health Checks

## Objective
Set up the complete structure for the Zapa Private service with health checks, logging, middleware, and comprehensive tests.

## Prerequisites
- Tasks 01-04 completed
- Database models and migrations working
- Configuration system in place

## Success Criteria
- [ ] Complete private service structure with proper layering
- [ ] Database connectivity and health checks
- [ ] Logging and middleware configuration
- [ ] Dependency injection for services
- [ ] Comprehensive tests for all components
- [ ] Tests passing locally and in CI/CD

## Files to Create

### services/private/app/__init__.py
```python
"""Zapa Private Service."""
__version__ = "0.1.0"
```

### services/private/app/main.py
```python
"""FastAPI application for Zapa Private service."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import database_manager
from app.core.exceptions import ZapaException
from app.api.v1.router import api_router

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Zapa Private service...")
    
    # Test database connection
    if await database_manager.health_check():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed!")
        
    yield
    
    # Shutdown
    logger.info("Shutting down Zapa Private service...")
    await database_manager.close()


app = FastAPI(
    title="Zapa Private API",
    description="Internal service for WhatsApp agent management",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# Security middleware
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.internal.company.com"]
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Add request timing headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests."""
    start_time = time.time()
    
    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
        }
    )
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} in {process_time:.3f}s",
        extra={
            "status_code": response.status_code,
            "process_time": process_time,
        }
    )
    
    return response


# Exception handlers
@app.exception_handler(ZapaException)
async def zapa_exception_handler(request: Request, exc: ZapaException):
    """Handle custom Zapa exceptions."""
    logger.error(f"Zapa exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected exception: {exc}", exc_info=True)
    
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
                "type": type(exc).__name__,
            }
        )


# Health check endpoints (not in API router for simplicity)
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "zapa-private",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def readiness_check():
    """Detailed readiness check with dependencies."""
    checks = {
        "database": await database_manager.health_check(),
        "service": True,
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "service": "zapa-private",
            "checks": checks,
        }
    )


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)
```

### services/private/app/core/exceptions.py
```python
"""Custom exceptions for Zapa Private service."""
from typing import Any, Dict, Optional


class ZapaException(Exception):
    """Base exception for Zapa application."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "ZAPA_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(ZapaException):
    """Validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class NotFoundError(ZapaException):
    """Resource not found error."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' not found",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(ZapaException):
    """Resource conflict error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details,
        )


class WhatsAppError(ZapaException):
    """WhatsApp Bridge related error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="WHATSAPP_ERROR",
            status_code=502,
            details=details,
        )


class LLMError(ZapaException):
    """LLM provider related error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            status_code=502,
            details=details,
        )


class AuthenticationError(ZapaException):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(ZapaException):
    """Authorization error."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
        )
```

### services/private/app/core/logging.py
```python
"""Logging configuration for Zapa Private service."""
import logging
import logging.config
import sys
from typing import Dict, Any

from app.core.config import settings


def setup_logging():
    """Set up logging configuration."""
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s "
                    "(%(filename)s:%(lineno)d)"
                ),
            },
            "json": {
                "format": (
                    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"logger": "%(name)s", "message": "%(message)s", '
                    '"module": "%(module)s", "line": %(lineno)d}'
                ),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "json" if settings.ENVIRONMENT == "production" else "standard",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
            },
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(logging_config)
    
    # Set uvicorn access log level
    if settings.ENVIRONMENT == "production":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

### services/private/app/core/database.py
```python
"""Database setup for Private service."""
from zapa_shared.database import DatabaseManager
from app.core.config import settings

# Global database manager instance
database_manager = DatabaseManager(settings)
```

### services/private/app/api/__init__.py
```python
"""API package."""
```

### services/private/app/api/v1/__init__.py
```python
"""API v1 package."""
```

### services/private/app/api/v1/router.py
```python
"""Main API router for v1."""
from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])

# Future routers will be added here:
# api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
# api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
```

### services/private/app/api/v1/endpoints/__init__.py
```python
"""API endpoints package."""
```

### services/private/app/api/v1/endpoints/health.py
```python
"""Health check endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import database_manager
from zapa_shared.database import get_db_session

router = APIRouter()


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db_session)):
    """Detailed health check with database and external service status."""
    checks = {
        "database": await database_manager.health_check(),
        "whatsapp_bridge": False,  # TODO: Implement when WhatsApp adapter is ready
        "redis": False,  # TODO: Implement when Redis is set up
    }
    
    # Try a simple database query
    try:
        result = db.execute("SELECT 1 as test").fetchone()
        checks["database_query"] = result is not None and result[0] == 1
    except Exception:
        checks["database_query"] = False
    
    all_healthy = all(checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "service": "zapa-private",
    }


@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"status": "pong"}
```

### services/private/app/api/dependencies.py
```python
"""Shared dependencies for API endpoints."""
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import database_manager

# Security
security = HTTPBearer(auto_error=False)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    async with database_manager.get_async_session() as session:
        yield session


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to verify admin authentication.
    
    TODO: Implement proper JWT verification when auth is ready.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # For now, just return a placeholder
    # TODO: Implement JWT verification
    return {"admin_id": "test", "permissions": ["admin"]}


async def verify_whatsapp_webhook(
    # TODO: Add webhook signature verification
) -> bool:
    """
    Dependency to verify WhatsApp webhook signatures.
    
    TODO: Implement webhook signature verification.
    """
    return True
```

### services/private/tests/test_main.py
```python
"""Tests for main FastAPI application."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test basic health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-private"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "test"


@patch('app.core.database.database_manager.health_check')
def test_ready_endpoint_healthy(mock_health_check, client):
    """Test readiness endpoint when all services are healthy."""
    mock_health_check.return_value = True
    
    response = client.get("/ready")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "zapa-private"
    assert data["checks"]["database"] is True
    assert data["checks"]["service"] is True


@patch('app.core.database.database_manager.health_check')
def test_ready_endpoint_unhealthy(mock_health_check, client):
    """Test readiness endpoint when database is unhealthy."""
    mock_health_check.return_value = False
    
    response = client.get("/ready")
    assert response.status_code == 503
    
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"] is False


def test_cors_headers(client):
    """Test CORS headers are set correctly."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3100",
            "Access-Control-Request-Method": "GET",
        }
    )
    
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_timing_middleware(client):
    """Test that timing middleware adds process time header."""
    response = client.get("/health")
    assert "X-Process-Time" in response.headers
    
    process_time = float(response.headers["X-Process-Time"])
    assert process_time > 0
    assert process_time < 1.0  # Should be very fast


def test_openapi_schema(client):
    """Test OpenAPI schema generation."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    schema = response.json()
    assert schema["info"]["title"] == "Zapa Private API"
    assert schema["info"]["version"] == "0.1.0"
    
    # Check that health endpoints are included
    paths = schema["paths"]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/health/detailed" in paths


def test_api_v1_router_included(client):
    """Test that API v1 router is properly included."""
    response = client.get("/api/v1/health/ping")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "pong"


@pytest.mark.asyncio
async def test_lifespan_events():
    """Test application lifespan events."""
    from app.main import lifespan
    
    # Mock the database manager
    with patch('app.main.database_manager') as mock_db_manager:
        mock_db_manager.health_check = AsyncMock(return_value=True)
        mock_db_manager.close = AsyncMock()
        
        # Test lifespan context manager
        async with lifespan(app):
            pass  # Simulate app running
        
        # Verify health check was called on startup
        mock_db_manager.health_check.assert_called_once()
        
        # Verify close was called on shutdown
        mock_db_manager.close.assert_called_once()
```

### services/private/tests/test_exceptions.py
```python
"""Tests for custom exceptions."""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

from app.core.exceptions import (
    ZapaException, ValidationError, NotFoundError, ConflictError,
    WhatsAppError, LLMError, AuthenticationError, AuthorizationError
)


def test_zapa_exception():
    """Test base ZapaException."""
    exc = ZapaException(
        message="Test error",
        error_code="TEST_ERROR",
        status_code=400,
        details={"field": "value"}
    )
    
    assert str(exc) == "Test error"
    assert exc.message == "Test error"
    assert exc.error_code == "TEST_ERROR"
    assert exc.status_code == 400
    assert exc.details == {"field": "value"}


def test_validation_error():
    """Test ValidationError."""
    exc = ValidationError("Invalid input", details={"field": "email"})
    
    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.status_code == 422
    assert exc.message == "Invalid input"
    assert exc.details == {"field": "email"}


def test_not_found_error():
    """Test NotFoundError."""
    exc = NotFoundError("User", "123")
    
    assert exc.error_code == "NOT_FOUND"
    assert exc.status_code == 404
    assert "User with identifier '123' not found" in exc.message
    assert exc.details["resource"] == "User"
    assert exc.details["identifier"] == "123"


def test_conflict_error():
    """Test ConflictError."""
    exc = ConflictError("Resource already exists")
    
    assert exc.error_code == "CONFLICT"
    assert exc.status_code == 409
    assert exc.message == "Resource already exists"


def test_whatsapp_error():
    """Test WhatsAppError."""
    exc = WhatsAppError("Bridge connection failed")
    
    assert exc.error_code == "WHATSAPP_ERROR"
    assert exc.status_code == 502
    assert exc.message == "Bridge connection failed"


def test_llm_error():
    """Test LLMError."""
    exc = LLMError("API key invalid")
    
    assert exc.error_code == "LLM_ERROR"
    assert exc.status_code == 502
    assert exc.message == "API key invalid"


def test_authentication_error():
    """Test AuthenticationError."""
    exc = AuthenticationError()
    
    assert exc.error_code == "AUTHENTICATION_ERROR"
    assert exc.status_code == 401
    assert exc.message == "Authentication failed"
    
    # With custom message
    exc2 = AuthenticationError("Invalid token")
    assert exc2.message == "Invalid token"


def test_authorization_error():
    """Test AuthorizationError."""
    exc = AuthorizationError()
    
    assert exc.error_code == "AUTHORIZATION_ERROR"
    assert exc.status_code == 403
    assert exc.message == "Access denied"


def test_exception_handler_integration():
    """Test exception handlers with FastAPI."""
    from app.main import app
    
    # Create a test endpoint that raises ZapaException
    @app.get("/test-error")
    async def test_error():
        raise ValidationError("Test validation error", details={"field": "test"})
    
    client = TestClient(app)
    response = client.get("/test-error")
    
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert data["message"] == "Test validation error"
    assert data["details"]["field"] == "test"


def test_general_exception_handler():
    """Test general exception handler for unexpected errors."""
    from app.main import app
    
    @app.get("/test-unexpected")
    async def test_unexpected():
        raise ValueError("Unexpected error")
    
    client = TestClient(app)
    response = client.get("/test-unexpected")
    
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "INTERNAL_SERVER_ERROR"
    # In test environment, should include error details
    assert "Unexpected error" in data["message"]
    assert data["type"] == "ValueError"
```

### services/private/tests/api/test_health.py
```python
"""Tests for health check endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@patch('app.api.v1.endpoints.health.database_manager.health_check')
def test_detailed_health_check_healthy(mock_health_check, client):
    """Test detailed health check when all services are healthy."""
    mock_health_check.return_value = True
    
    # Mock database session and query result
    with patch('app.api.v1.endpoints.health.get_db_session') as mock_get_db:
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.__getitem__ = MagicMock(return_value=1)
        mock_db.execute.return_value.fetchone.return_value = mock_result
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)
        
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "degraded"  # WhatsApp and Redis are False
        assert data["service"] == "zapa-private"
        assert data["checks"]["database"] is True
        assert data["checks"]["database_query"] is True
        assert data["checks"]["whatsapp_bridge"] is False
        assert data["checks"]["redis"] is False


@patch('app.api.v1.endpoints.health.database_manager.health_check')
def test_detailed_health_check_database_error(mock_health_check, client):
    """Test detailed health check when database query fails."""
    mock_health_check.return_value = True
    
    # Mock database session that raises exception
    with patch('app.api.v1.endpoints.health.get_db_session') as mock_get_db:
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database error")
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)
        
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] is True  # Manager health check passed
        assert data["checks"]["database_query"] is False  # Query failed


def test_ping_endpoint(client):
    """Test simple ping endpoint."""
    response = client.get("/api/v1/health/ping")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "pong"


def test_health_endpoints_in_openapi(client):
    """Test that health endpoints are documented in OpenAPI."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    schema = response.json()
    paths = schema["paths"]
    
    # Check that our health endpoints are documented
    assert "/api/v1/health/detailed" in paths
    assert "/api/v1/health/ping" in paths
    
    # Check endpoint details
    detailed_endpoint = paths["/api/v1/health/detailed"]["get"]
    assert detailed_endpoint["tags"] == ["health"]
    assert "Detailed health check" in detailed_endpoint["summary"]
```

### Update services/private/pyproject.toml
```toml
[project]
dependencies = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "httpx==0.26.0",
    "sqlalchemy[asyncio]==2.0.25",
    "asyncpg==0.29.0",
    "redis==5.0.1",
    "zapa-shared @ file://../../shared",
]
```

## Commands to Run

```bash
# Install updated dependencies
cd services/private
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/test_main.py -v
uv run pytest tests/test_exceptions.py -v
uv run pytest tests/api/test_health.py -v

# Run the service
uv run uvicorn app.main:app --reload --port 8001

# Test endpoints manually
curl http://localhost:8001/health
curl http://localhost:8001/ready
curl http://localhost:8001/api/v1/health/detailed
curl http://localhost:8001/api/v1/health/ping

# Check OpenAPI docs
open http://localhost:8001/docs

# Run with coverage
uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

## Verification

1. Service starts without errors
2. All health endpoints return correct responses
3. Database connectivity works
4. Middleware adds timing headers
5. Exception handlers work correctly
6. CORS is configured properly
7. Logging outputs structured logs
8. Tests achieve ≥90% coverage
9. OpenAPI documentation is generated

## Architecture Verification

Check that the service follows the "Plumbing + Intelligence" pattern:
- **API Layer**: Clean endpoints with no business logic
- **Core Layer**: Configuration, exceptions, database setup
- **Future Services**: Will contain business logic
- **Future Adapters**: Will handle external integrations

## Next Steps

After private service structure is complete, proceed to Task 06: WhatsApp Bridge Adapter with Integration Tests.