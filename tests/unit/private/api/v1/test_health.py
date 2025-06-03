"""Tests for private API health endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.private.api.v1.health import get_db_session
from app.private.main import app


@pytest.fixture
def client():
    """Create test client for private app."""
    return TestClient(app)


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    assert "environment" in data


@patch("app.private.api.v1.health.get_database_manager")
@patch("httpx.AsyncClient")
def test_readiness_check_all_healthy(mock_httpx_client, mock_get_db_manager, client):
    """Test readiness check when all services are healthy."""
    # Mock database manager
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.return_value = True
    mock_get_db_manager.return_value = mock_db_manager

    # Mock httpx client for WhatsApp Bridge
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert data["checks"]["database"]["status"] == "healthy"
    assert data["checks"]["whatsapp_bridge"]["status"] == "healthy"


@patch("app.private.api.v1.health.get_database_manager")
@patch("httpx.AsyncClient")
def test_readiness_check_database_unhealthy(
    mock_httpx_client, mock_get_db_manager, client
):
    """Test readiness check when database is unhealthy."""
    # Mock database manager - unhealthy
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.return_value = False
    mock_get_db_manager.return_value = mock_db_manager

    # Mock httpx client for WhatsApp Bridge - healthy
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/ready")
    assert response.status_code == 503

    data = response.json()["detail"]
    assert data["status"] == "not_ready"
    assert data["checks"]["database"]["status"] == "unhealthy"
    assert data["checks"]["whatsapp_bridge"]["status"] == "healthy"


@patch("app.private.api.v1.health.get_database_manager")
@patch("httpx.AsyncClient")
def test_readiness_check_bridge_unhealthy(
    mock_httpx_client, mock_get_db_manager, client
):
    """Test readiness check when WhatsApp Bridge is unhealthy."""
    # Mock database manager - healthy
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.return_value = True
    mock_get_db_manager.return_value = mock_db_manager

    # Mock httpx client for WhatsApp Bridge - unhealthy
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/ready")
    assert response.status_code == 503

    data = response.json()["detail"]
    assert data["status"] == "not_ready"
    assert data["checks"]["database"]["status"] == "healthy"
    assert data["checks"]["whatsapp_bridge"]["status"] == "unhealthy"


def test_database_check_success(client):
    """Test database check endpoint success."""
    # Mock database session
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_session.execute.return_value = mock_result

    # Override dependency
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        response = client.get("/api/v1/database")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["connection_test"] == "passed"
    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()


def test_database_check_failure(client):
    """Test database check endpoint failure."""
    # Mock database session to raise exception
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("Connection failed")

    # Override dependency
    app.dependency_overrides[get_db_session] = lambda: mock_session

    try:
        response = client.get("/api/v1/database")
        assert response.status_code == 500

        data = response.json()
        assert data["error"] == "DATABASE_ERROR"
        assert "Connection failed" in data["message"]
    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()


@patch("httpx.AsyncClient")
def test_whatsapp_bridge_check_success(mock_httpx_client, client):
    """Test WhatsApp Bridge check endpoint success."""
    # Mock successful responses
    mock_health_response = MagicMock()
    mock_health_response.status_code = 200

    mock_status_response = MagicMock()
    mock_status_response.status_code = 200
    mock_status_response.json.return_value = {"status": "connected"}

    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = [mock_health_response, mock_status_response]
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/whatsapp-bridge")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["health_check"] == "passed"
    assert data["bridge_data"] == {"status": "connected"}


@patch("httpx.AsyncClient")
def test_whatsapp_bridge_check_failure(mock_httpx_client, client):
    """Test WhatsApp Bridge check endpoint failure."""
    # Mock failed health response
    mock_health_response = MagicMock()
    mock_health_response.status_code = 503

    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_health_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/whatsapp-bridge")
    assert response.status_code == 503

    data = response.json()
    assert data["error"] == "WHATSAPP_BRIDGE_ERROR"


@patch("httpx.AsyncClient")
def test_whatsapp_bridge_check_connection_error(mock_httpx_client, client):
    """Test WhatsApp Bridge check with connection error."""
    # Mock connection error
    mock_client_instance = AsyncMock()
    mock_client_instance.get.side_effect = Exception("Connection refused")
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    response = client.get("/api/v1/whatsapp-bridge")
    assert response.status_code == 503

    data = response.json()
    assert data["error"] == "WHATSAPP_BRIDGE_ERROR"
    assert "Connection refused" in data["message"]
