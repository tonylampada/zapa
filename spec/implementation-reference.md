# Implementation Reference

This document preserves valuable implementation details from the v1 tasks that may be useful during development.

## Security Implementation

### Password Security (from v1 Task 07)
```python
# Use bcrypt for password hashing
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

### Account Lockout Mechanism
```python
# Track failed login attempts
async def track_failed_login(username: str, redis_client):
    key = f"failed_login:{username}"
    count = await redis_client.incr(key)
    await redis_client.expire(key, 900)  # 15 minutes
    
    if count >= 5:
        # Lock account
        await redis_client.setex(f"locked:{username}", 3600, "1")
        return True
    return False

# Check if account is locked
async def is_account_locked(username: str, redis_client):
    return await redis_client.get(f"locked:{username}") is not None
```

### Rate Limiting Middleware
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")
async def login(credentials: LoginRequest):
    # Login logic
    pass
```

## Docker Configuration

### Multi-Stage Python Dockerfile (from v1 Task 17)
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install --upgrade pip setuptools wheel
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Runtime stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

USER appuser
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Development Setup
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: zapa_dev
      POSTGRES_USER: devuser
      POSTGRES_PASSWORD: devpass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devuser -d zapa_dev"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db

volumes:
  postgres_data:
```

### Makefile for Common Commands
```makefile
.PHONY: build up down logs clean test

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

test:
	docker-compose run --rm backend pytest

migrate:
	docker-compose run --rm backend alembic upgrade head
```

## Testing Patterns

### Mock Service Fixtures (from v1 Task 04)
```python
# tests/fixtures/mock_services.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_openai():
    """Mock OpenAI client for testing."""
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(
            message=MagicMock(
                content="Test response",
                function_call=None
            )
        )]
    ))
    return mock

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        async def get(self, key):
            return self.data.get(key)
        
        async def setex(self, key, ttl, value):
            self.data[key] = value
            return True
        
        async def delete(self, key):
            self.data.pop(key, None)
            return True
    
    return MockRedis()
```

### Integration Test Base
```python
# tests/integration/base.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

class IntegrationTestBase:
    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    async def authenticated_client(self, client, test_user):
        token = await self.get_auth_token(test_user)
        client.headers["Authorization"] = f"Bearer {token}"
        yield client
    
    @pytest.fixture
    async def test_user(self, db_session):
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("testpass123")
        )
        db_session.add(user)
        await db_session.commit()
        return user
```

## Monitoring Implementation

### Health Check System (from v1 Task 13)
```python
from enum import Enum
from typing import Dict, List
import asyncio
from datetime import datetime

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthChecker:
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name: str, check_func):
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict:
        results = {}
        tasks = []
        
        for name, check_func in self.checks.items():
            task = asyncio.create_task(self._run_single_check(name, check_func))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        for task in tasks:
            name, result = task.result()
            results[name] = result
        
        return {
            "status": self._overall_status(results),
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results
        }
    
    async def _run_single_check(self, name: str, check_func):
        try:
            start = asyncio.get_event_loop().time()
            result = await check_func()
            duration = asyncio.get_event_loop().time() - start
            
            return name, {
                "status": HealthStatus.HEALTHY.value,
                "duration_ms": round(duration * 1000, 2),
                **result
            }
        except Exception as e:
            return name, {
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e)
            }
```

## Middleware Configuration

### Request Timing Middleware (from v1 Task 02)
```python
import time
from fastapi import Request

async def add_timing_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

### Global Exception Handler
```python
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__
        }
    )
```

## Frontend Configuration

### Vue Router with Guards (from v1 Task 08)
```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true }
    }
  ]
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})
```

### API Client with Interceptors
```javascript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
    }
    return Promise.reject(error)
  }
)
```

## Database Migrations

### Alembic Setup (from v1 Task 03)
```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add user table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration Script Template
```python
"""Add indexes for performance

Revision ID: xxxxx
Revises: yyyyy
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add indexes
    op.create_index('idx_messages_user_created', 'messages', ['user_id', 'created_at'])
    op.create_index('idx_messages_search', 'messages', ['content'], postgresql_using='gin')

def downgrade():
    op.drop_index('idx_messages_user_created')
    op.drop_index('idx_messages_search')
```

## Testing Requirements

From v1 tasks, the following test coverage requirements were specified:
- Overall coverage: 90%+
- Unit tests for all services
- Integration tests for API endpoints
- E2E tests for critical user flows
- Performance benchmarks for database queries
- Security tests for authentication and authorization

## Additional Notes

- Use environment variables for all configuration
- Implement structured logging with correlation IDs
- Use connection pooling for database connections
- Implement circuit breakers for external service calls
- Add OpenTelemetry for distributed tracing
- Use feature flags for gradual rollouts