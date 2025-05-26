"""Tests for private main application."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.private.main import app
from app.private.api.v1.health import get_db_session
from app.core.exceptions import ZapaException, DatabaseError


@pytest.fixture
def client():
    """Create test client for private app."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns service information."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["service"] == "Zapa Private API"
    assert "version" in data
    assert "environment" in data


def test_docs_available_in_non_production(client):
    """Test that docs are available in non-production environment."""
    # In test environment, docs should be available
    response = client.get("/docs")
    assert response.status_code == 200


def test_cors_headers(client):
    """Test CORS headers are set correctly."""
    response = client.get("/", headers={"Origin": "http://localhost:3100"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_timing_middleware(client):
    """Test timing middleware adds process time header."""
    response = client.get("/")
    assert response.status_code == 200
    assert "x-process-time" in response.headers
    
    # Process time should be a valid float
    process_time = float(response.headers["x-process-time"])
    assert process_time >= 0


@patch("app.private.main.logger")
def test_request_logging_middleware(mock_logger, client):
    """Test request logging middleware logs requests."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    # Should have logged request and response
    assert mock_logger.info.call_count >= 2
    
    # Check that request was logged
    request_calls = [call for call in mock_logger.info.call_args_list 
                    if "Request:" in str(call)]
    assert len(request_calls) >= 1
    
    # Check that response was logged  
    response_calls = [call for call in mock_logger.info.call_args_list 
                     if "Response:" in str(call)]
    assert len(response_calls) >= 1


def test_zapa_exception_handler(client):
    """Test custom exception handler for ZapaException."""
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
        assert "Database connectivity failed" in data["message"]
        assert "Connection failed" in data["message"]
    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()


def test_general_exception_handler(client):
    """Test general exception handler for unexpected errors."""
    # Mock database session to raise a general exception
    mock_session = MagicMock()
    mock_session.execute.side_effect = RuntimeError("Unexpected error")
    
    # Override dependency
    app.dependency_overrides[get_db_session] = lambda: mock_session
    
    try:
        response = client.get("/api/v1/database")
        assert response.status_code == 500
        
        data = response.json()
        # The health endpoint will catch and wrap in DatabaseError, so it's handled by zapa_exception_handler
        assert data["error"] == "DATABASE_ERROR"
        assert "Database connectivity failed" in data["message"]
        assert "Unexpected error" in data["message"]
    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()


@patch("app.private.main.get_database_manager")
@patch("app.private.main.logger")
def test_lifespan_startup_success(mock_logger, mock_get_db_manager):
    """Test successful application startup."""
    # Mock database manager
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.return_value = True
    mock_get_db_manager.return_value = mock_db_manager
    
    # Create app instance to trigger lifespan
    with TestClient(app):
        pass
    
    # Should log startup and database success
    startup_calls = [call for call in mock_logger.info.call_args_list 
                    if "Starting Zapa Private" in str(call)]
    assert len(startup_calls) >= 1
    
    db_success_calls = [call for call in mock_logger.info.call_args_list 
                       if "Database connection successful" in str(call)]
    assert len(db_success_calls) >= 1


@patch("app.private.main.get_database_manager")
@patch("app.private.main.logger")
def test_lifespan_startup_database_failure(mock_logger, mock_get_db_manager):
    """Test application startup with database failure."""
    # Mock database manager to fail
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.return_value = False
    mock_get_db_manager.return_value = mock_db_manager
    
    # Create app instance to trigger lifespan
    with TestClient(app):
        pass
    
    # Should log database failure
    db_failure_calls = [call for call in mock_logger.error.call_args_list 
                       if "Database connection failed" in str(call)]
    assert len(db_failure_calls) >= 1


@patch("app.private.main.get_database_manager")
@patch("app.private.main.logger")
def test_lifespan_startup_database_exception(mock_logger, mock_get_db_manager):
    """Test application startup with database exception."""
    # Mock database manager to raise exception
    mock_db_manager = AsyncMock()
    mock_db_manager.health_check.side_effect = Exception("Connection error")
    mock_get_db_manager.return_value = mock_db_manager
    
    # Create app instance to trigger lifespan
    with TestClient(app):
        pass
    
    # Should log database error
    db_error_calls = [call for call in mock_logger.error.call_args_list 
                     if "Database connection error" in str(call)]
    assert len(db_error_calls) >= 1


def test_api_router_included(client):
    """Test that API router is properly included."""
    # Health endpoint should be available through API router
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    # Should return health check data
    data = response.json()
    assert data["status"] == "healthy"