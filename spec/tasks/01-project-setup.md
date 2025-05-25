# Task 01: Project Setup & Scaffolding with Tests

## Objective
Initialize the project structure with UV for Python dependencies, basic test infrastructure, and GitHub Actions CI from the start.

## Requirements
- Use UV for Python dependency management
- Create directory structure for backend, frontend, and infrastructure
- Set up initial tests that can run
- Configure GitHub Actions to run tests on every push
- Ensure tests pass both locally and in CI before proceeding

## Directory Structure to Create

```
zapa/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   ├── adapters/
│   │   │   └── __init__.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   └── core/
│   │       └── __init__.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_health.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .gitignore
├── frontend/
│   ├── src/
│   ├── public/
│   ├── tests/
│   ├── package.json
│   ├── Dockerfile
│   └── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker/
│   └── docker-compose.yml
├── docs/
├── scripts/
├── .env.example
└── .gitignore (root)
```

## Files to Create

### backend/pyproject.toml
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

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
asyncio_mode = "auto"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/conftest.py"]

[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I"]
```

### backend/app/main.py (minimal for testing)
```python
from fastapi import FastAPI

app = FastAPI(
    title="WhatsApp Agent API",
    version="0.1.0",
    description="Backend API for WhatsApp Agent System"
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-agent-backend"}
```

### backend/tests/conftest.py
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def async_client():
    """Create an async test client for the FastAPI app."""
    from httpx import AsyncClient
    return AsyncClient(app=app, base_url="http://test")
```

### backend/tests/test_health.py
```python
def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "whatsapp-agent-backend"

def test_app_metadata(client):
    """Test that app has correct metadata."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "WhatsApp Agent API"
    assert data["info"]["version"] == "0.1.0"
```

### .github/workflows/ci.yml
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    
    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
    
    - name: Install dependencies
      run: |
        uv venv
        uv pip install -e . --all-extras
        uv pip install pytest pytest-asyncio pytest-cov httpx
    
    - name: Run linting
      run: |
        uv run ruff check app tests
        uv run black --check app tests
    
    - name: Run tests with coverage
      run: |
        uv run pytest tests -v --cov=app --cov-report=term-missing --cov-report=xml
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
        flags: backend
        name: backend-coverage

  test-frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run tests
      run: npm test
    
    - name: Build
      run: npm run build
```

### Root .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.env
*.egg-info/
.coverage
coverage.xml
htmlcov/
.pytest_cache/

# UV
.uv/

# Node
node_modules/
dist/
.DS_Store
npm-debug.log*
yarn-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# Docker
.docker/

# Logs
*.log

# Database
*.db
*.sqlite3

# OS
.DS_Store
Thumbs.db
```

### .env.example
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/whatsapp_agent

# Security
SECRET_KEY=your-secret-key-here
ADMIN_TOKEN_SECRET=your-admin-token-secret

# WhatsApp Bridge
WHATSAPP_API_URL=http://whatsapp-bridge:3000
WHATSAPP_API_KEY=your-whatsapp-api-key

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
```

### backend/Makefile
```makefile
.PHONY: install test lint format run

install:
	uv venv
	uv pip install -e . --all-extras

test:
	uv run pytest tests -v

test-cov:
	uv run pytest tests -v --cov=app --cov-report=term-missing

lint:
	uv run ruff check app tests
	uv run black --check app tests

format:
	uv run black app tests
	uv run ruff check --fix app tests

run:
	uv run uvicorn app.main:app --reload

clean:
	rm -rf .uv __pycache__ .pytest_cache .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
```

## Tests to Verify

1. **Health Check Test** - Verifies the basic FastAPI app is working
2. **OpenAPI Test** - Ensures API documentation is generated correctly
3. **CI Pipeline Test** - Confirms tests run in GitHub Actions

## Success Criteria
- [ ] UV is set up and dependencies install correctly
- [ ] Basic FastAPI app with health endpoint works
- [ ] Tests pass locally using `uv run pytest`
- [ ] GitHub Actions workflow is configured
- [ ] Tests pass in GitHub Actions
- [ ] Code passes linting (black, ruff)
- [ ] Coverage reporting works

## Commands to Run
```bash
# Install dependencies
cd backend
uv venv
uv pip install -e . --all-extras

# Run tests locally
uv run pytest tests -v

# Run linting
uv run black --check app tests
uv run ruff check app tests

# Run with coverage
uv run pytest tests -v --cov=app --cov-report=term-missing
```