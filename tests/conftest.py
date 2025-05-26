import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from private_main import app as private_app
from public_main import app as public_app


@pytest.fixture
def private_client():
    """Create a test client for the private FastAPI app."""
    return TestClient(private_app)


@pytest.fixture
def public_client():
    """Create a test client for the public FastAPI app."""
    return TestClient(public_app)


@pytest.fixture
async def private_async_client():
    """Create an async test client for private app."""
    async with AsyncClient(app=private_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def public_async_client():
    """Create an async test client for public app."""
    async with AsyncClient(app=public_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "False")
    return monkeypatch
