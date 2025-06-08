import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing settings
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_12345678901234567890"
os.environ["ENCRYPTION_KEY"] = "test_encryption_key_for_testing_1234567890123456"
os.environ["ADMIN_TOKEN_SECRET"] = "test_admin_token_secret_for_testing_123456789012"
os.environ["PRIVATE_SERVICE_SECRET"] = (
    "test_private_service_secret_for_testing_12345678"
)
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Import settings modules after setting env vars
from app.config.private import PrivateSettings  # noqa: E402
from app.config.public import PublicSettings  # noqa: E402

# Create test settings instances
private_test_settings = PrivateSettings()
public_test_settings = PublicSettings()


@pytest.fixture(autouse=True)
def mock_private_settings():
    """Automatically mock private settings for all tests."""
    with patch("app.config.private.settings", private_test_settings):
        yield


@pytest.fixture(autouse=True)
def mock_public_settings():
    """Automatically mock public settings for all tests."""
    with patch("app.config.public.settings", public_test_settings):
        yield


# Import apps after mocking settings
from private_main import app as private_app  # noqa: E402
from public_main import app as public_app  # noqa: E402


@pytest.fixture
def private_client():
    """Create a test client for the private FastAPI app."""
    return TestClient(private_app)


@pytest.fixture
def public_client():
    """Create a test client for the public FastAPI app."""
    return TestClient(public_app)


@pytest.fixture
def private_async_client():
    """Create an async test client for private app."""
    # For testing async endpoints, we still use TestClient
    # which handles async routes internally
    return TestClient(private_app)


@pytest.fixture
def public_async_client():
    """Create an async test client for public app."""
    # For testing async endpoints, we still use TestClient
    # which handles async routes internally
    return TestClient(public_app)


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "False")
    return monkeypatch
