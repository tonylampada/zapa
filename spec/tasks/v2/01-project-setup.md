# Task 01: Project Setup with Dual Service Architecture

## Objective
Initialize the project structure for two FastAPI services (Private and Public), Vue.js frontends, shared components, and GitHub Actions CI/CD that runs tests on every push.

## Success Criteria
- [ ] UV installed and working for Python dependencies
- [ ] Basic project structure created for both services
- [ ] Health check endpoints working for both services
- [ ] Tests passing locally for both services
- [ ] GitHub Actions running tests on push
- [ ] Linting (black, ruff, ESLint) configured and passing

## Directory Structure

```
zapa/
├── services/
│   ├── private/                 # Zapa Private Service
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── services/
│   │   │   ├── adapters/
│   │   │   └── core/
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   └── test_health.py
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   └── public/                  # Zapa Public Service
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── api/
│       │   ├── services/
│       │   ├── adapters/
│       │   └── core/
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── conftest.py
│       │   └── test_health.py
│       ├── pyproject.toml
│       └── Dockerfile
│
├── frontend/
│   ├── private/                 # Admin Frontend
│   │   ├── src/
│   │   ├── public/
│   │   ├── tests/
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── public/                  # User Frontend
│   │   ├── src/
│   │   ├── public/
│   │   ├── tests/
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   └── shared/                  # Shared Components
│       ├── src/
│       ├── package.json
│       └── tsconfig.json
│
├── shared/                      # Shared Python Code
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── schemas/
│   │   └── __init__.py
│   └── pyproject.toml
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docker/
│   └── docker-compose.yml
│
├── scripts/
│   ├── setup.sh
│   └── test-all.sh
│
└── .gitignore
```

## Files to Create

### .gitignore (root)
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
.env
*.egg-info/
.coverage
coverage.xml
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# UV
.uv/

# Node
node_modules/
dist/
.DS_Store
npm-debug.log*
yarn-debug.log*
.pnpm-debug.log*

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Testing
test-results/
playwright-report/

# OS
.DS_Store
Thumbs.db

# Docker
.docker/

# Logs
*.log
logs/

# Database
*.db
*.sqlite3
```

### services/private/pyproject.toml
```toml
[project]
name = "zapa-private"
version = "0.1.0"
description = "Zapa Private Service - Internal WhatsApp Agent API"
requires-python = ">=3.10"
dependencies = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "httpx==0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.4",
    "pytest-asyncio==0.23.3",
    "pytest-cov==4.1.0",
    "pytest-env==1.1.3",
    "black==23.12.1",
    "ruff==0.1.11",
    "mypy==1.8.0",
    "types-redis==4.6.0.20240106",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_mode = "auto"
env = [
    "ENVIRONMENT=test",
    "INTEGRATION_TEST_WHATSAPP=false",
    "INTEGRATION_TEST_OPENAI=false",
    "INTEGRATION_TEST_ANTHROPIC=false",
    "INTEGRATION_TEST_GOOGLE=false",
]

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/conftest.py"]

[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "UP", "B"]
ignore = ["E501"]  # line too long

[tool.mypy]
python_version = "3.10"
ignore_missing_imports = true
```

### services/private/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Zapa Private API",
    description="Internal service for WhatsApp agent management",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS for admin frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "zapa-private",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add checks for database, redis, whatsapp bridge
    return {
        "status": "ready",
        "service": "zapa-private",
    }
```

### services/private/app/core/config.py
```python
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Zapa Private"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3100", "http://localhost:3000"]
    
    # Security
    SECRET_KEY: str = "development-secret-key-change-in-production"
    ADMIN_TOKEN_SECRET: str = "admin-secret-change-in-production"
    
    # External Services
    WHATSAPP_BRIDGE_URL: str = "http://localhost:3000"
    DATABASE_URL: str = "postgresql://zapa:zapa@localhost:5432/zapa"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Integration Tests
    INTEGRATION_TEST_WHATSAPP: bool = False
    INTEGRATION_TEST_OPENAI: bool = False
    INTEGRATION_TEST_ANTHROPIC: bool = False
    INTEGRATION_TEST_GOOGLE: bool = False


settings = Settings()
```

### services/private/tests/conftest.py
```python
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "False")
    return monkeypatch
```

### services/private/tests/test_health.py
```python
import pytest
from fastapi import status


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-private"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_readiness_check(client):
    """Test the readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "zapa-private"


@pytest.mark.asyncio
async def test_health_check_async(async_client):
    """Test health check with async client."""
    response = await async_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "healthy"


def test_openapi_schema(client):
    """Test that OpenAPI schema is generated."""
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    
    schema = response.json()
    assert schema["info"]["title"] == "Zapa Private API"
    assert schema["info"]["version"] == "0.1.0"
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]


def test_cors_headers(client):
    """Test CORS headers are set correctly."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3100"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
```

### services/public/pyproject.toml
```toml
[project]
name = "zapa-public"
version = "0.1.0"
description = "Zapa Public Service - User-facing WhatsApp Agent API"
requires-python = ">=3.10"
dependencies = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "httpx==0.26.0",
    "python-jose[cryptography]==3.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.4",
    "pytest-asyncio==0.23.3",
    "pytest-cov==4.1.0",
    "pytest-env==1.1.3",
    "black==23.12.1",
    "ruff==0.1.11",
    "mypy==1.8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_mode = "auto"
env = [
    "ENVIRONMENT=test",
]

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/conftest.py"]

[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "UP", "B"]
ignore = ["E501"]
```

### services/public/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Zapa Public API",
    description="Public API for WhatsApp agent user access",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS for public frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "zapa-public",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add checks for database, redis
    return {
        "status": "ready",
        "service": "zapa-public",
    }
```

### services/public/tests/test_health.py
```python
import pytest
from fastapi import status


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-public"
    assert data["version"] == "0.1.0"


def test_readiness_check(client):
    """Test the readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "zapa-public"


def test_openapi_schema(client):
    """Test that OpenAPI schema is generated."""
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    
    schema = response.json()
    assert schema["info"]["title"] == "Zapa Public API"
    assert "/health" in schema["paths"]
```

### .github/workflows/ci.yml
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  PYTHON_VERSION: "3.10"
  NODE_VERSION: "18"

jobs:
  test-private-service:
    name: Test Private Service
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/private
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
    
    - name: Create virtual environment
      run: uv venv
    
    - name: Install dependencies
      run: |
        uv pip install -e ".[dev]"
    
    - name: Run linting
      run: |
        uv run black --check app tests
        uv run ruff check app tests
    
    - name: Run type checking
      run: |
        uv run mypy app
    
    - name: Run tests with coverage
      run: |
        uv run pytest -v --cov=app --cov-report=term-missing --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./services/private/coverage.xml
        flags: private-service
        name: private-service-coverage

  test-public-service:
    name: Test Public Service
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/public
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
    
    - name: Create virtual environment
      run: uv venv
    
    - name: Install dependencies
      run: |
        uv pip install -e ".[dev]"
    
    - name: Run linting
      run: |
        uv run black --check app tests
        uv run ruff check app tests
    
    - name: Run type checking
      run: |
        uv run mypy app
    
    - name: Run tests with coverage
      run: |
        uv run pytest -v --cov=app --cov-report=term-missing --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./services/public/coverage.xml
        flags: public-service
        name: public-service-coverage

  test-shared:
    name: Test Shared Components
    runs-on: ubuntu-latest
    if: false  # Enable when shared components are added
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install uv
      uses: astral-sh/setup-uv@v3
    
    - name: Test shared Python components
      run: |
        cd shared
        uv venv
        uv pip install -e ".[dev]"
        uv run pytest -v

  all-tests-pass:
    name: All Tests Pass
    needs: [test-private-service, test-public-service]
    runs-on: ubuntu-latest
    steps:
    - name: All tests passed
      run: echo "All tests passed successfully!"
```

### scripts/setup.sh
```bash
#!/bin/bash
set -e

echo "🚀 Setting up Zapa development environment..."

# Check for required tools
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed."; exit 1; }

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Set up Python services
echo "🐍 Setting up Python services..."

# Private service
echo "  - Setting up private service..."
cd services/private
uv venv
uv pip install -e ".[dev]"

# Public service
echo "  - Setting up public service..."
cd ../public
uv venv
uv pip install -e ".[dev]"

cd ../..

echo "✅ Setup complete!"
echo ""
echo "To run tests:"
echo "  ./scripts/test-all.sh"
echo ""
echo "To run services:"
echo "  cd services/private && uv run uvicorn app.main:app --reload --port 8001"
echo "  cd services/public && uv run uvicorn app.main:app --reload --port 8002"
```

### scripts/test-all.sh
```bash
#!/bin/bash
set -e

echo "🧪 Running all tests..."

# Test private service
echo ""
echo "Testing Private Service..."
cd services/private
uv run black --check app tests
uv run ruff check app tests
uv run pytest -v --cov=app --cov-report=term-missing

# Test public service
echo ""
echo "Testing Public Service..."
cd ../public
uv run black --check app tests
uv run ruff check app tests
uv run pytest -v --cov=app --cov-report=term-missing

cd ../..

echo ""
echo "✅ All tests passed!"
```

## Commands to Run

```bash
# Make scripts executable
chmod +x scripts/setup.sh scripts/test-all.sh

# Run setup
./scripts/setup.sh

# Run all tests
./scripts/test-all.sh

# Or test individual services
cd services/private
uv run pytest -v

cd services/public
uv run pytest -v

# Run services
cd services/private
uv run uvicorn app.main:app --reload --port 8001

cd services/public
uv run uvicorn app.main:app --reload --port 8002
```

## Verification

1. Both services start without errors
2. Health endpoints return correct responses:
   - http://localhost:8001/health (Private)
   - http://localhost:8002/health (Public)
3. All tests pass locally
4. GitHub Actions workflow succeeds
5. Code coverage is reported

## Next Steps

After this task is complete and CI/CD is passing, proceed to Task 02: Database Models and Schemas.