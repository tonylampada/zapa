"""Fixtures for adapter tests."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")


@pytest.fixture(autouse=True)
def integration_test_env(monkeypatch):
    """Auto-set integration test environment variables for tests."""
    # Ensure integration tests are off by default
    if "INTEGRATION_TEST_WHATSAPP" not in os.environ:
        monkeypatch.setenv("INTEGRATION_TEST_WHATSAPP", "false")


@pytest.fixture
def db():
    """Create test database session."""
    # Use SQLite in-memory for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Create tables
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def mock_redis(monkeypatch):
    """Mock Redis for tests."""
    mock_redis_instance = AsyncMock()
    mock_redis_instance.ping = AsyncMock(return_value=True)
    mock_redis_instance.lpush = AsyncMock()
    mock_redis_instance.rpoplpush = AsyncMock(return_value=None)
    mock_redis_instance.lrange = AsyncMock(return_value=[])
    mock_redis_instance.lrem = AsyncMock()
    mock_redis_instance.llen = AsyncMock(return_value=0)
    mock_redis_instance.delete = AsyncMock()
    mock_redis_instance.expire = AsyncMock()
    mock_redis_instance.close = AsyncMock()
    mock_redis_instance.info = AsyncMock(
        return_value={
            "used_memory_human": "10MB",
            "connected_clients": 1,
        }
    )

    async def mock_from_url(*args, **kwargs):
        return mock_redis_instance

    monkeypatch.setattr("app.services.message_queue.redis.from_url", mock_from_url)
    monkeypatch.setattr("app.services.integration_monitor.redis.from_url", mock_from_url)

    return mock_redis_instance


@pytest.fixture
def mock_whatsapp_adapter(monkeypatch):
    """Mock WhatsApp adapter for tests."""
    mock_adapter = AsyncMock()
    mock_adapter.send_message = AsyncMock(
        return_value={"message_id": "test_response_123", "status": "sent"}
    )
    mock_adapter.get_sessions = AsyncMock(
        return_value=[
            MagicMock(
                session_id="+1234567890",
                status="connected",
                phone_number="+1234567890",
            )
        ]
    )
    mock_adapter.create_session = AsyncMock(
        return_value=MagicMock(
            session_id="+1234567890",
            status="disconnected",
        )
    )
    mock_adapter.get_qr_code = AsyncMock(return_value="mock_qr_code_data")

    # Make it work as async context manager
    mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
    mock_adapter.__aexit__ = AsyncMock(return_value=None)

    def mock_adapter_init(*args, **kwargs):
        return mock_adapter

    monkeypatch.setattr("app.adapters.whatsapp.WhatsAppBridgeAdapter", mock_adapter_init)
    monkeypatch.setattr("app.services.agent_service.WhatsAppBridgeAdapter", mock_adapter_init)

    return mock_adapter


@pytest.fixture
def admin_headers(db):
    """Create admin user and return auth headers."""
    from app.core.security import create_access_token
    from app.models import User

    # Create admin user
    admin = User(
        phone_number="+1234567890",
        display_name="Test Admin",
        is_active=True,
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # Create token
    token = create_access_token(data={"sub": str(admin.id), "is_admin": True})

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    """Create test client for private API."""
    from fastapi.testclient import TestClient

    from app.private.main import app

    return TestClient(app)
