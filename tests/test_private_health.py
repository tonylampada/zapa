import pytest
from fastapi import status


def test_private_health_check(private_client):
    """Test the private service health check endpoint."""
    response = private_client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-private"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_private_readiness_check(private_client):
    """Test the private service readiness check endpoint."""
    # Note: This may return 503 due to external dependencies in test environment
    response = private_client.get("/api/v1/ready")
    
    # Accept both 200 (ready) and 503 (not ready) as valid responses
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
    
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "zapa-private"
    else:
        # For 503, data is in detail field
        data = response.json()["detail"]
        assert data["status"] == "not_ready"
        assert data["service"] == "zapa-private"


@pytest.mark.asyncio
async def test_private_health_check_async(private_async_client):
    """Test private health check with async client."""
    response = await private_async_client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"


def test_private_openapi_schema(private_client):
    """Test that OpenAPI schema is generated for private service."""
    response = private_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    schema = response.json()
    assert schema["info"]["title"] == "Zapa Private API"
    assert schema["info"]["version"] == "0.1.0"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/ready" in schema["paths"]


def test_private_cors_headers(private_client):
    """Test CORS headers are set correctly for private service."""
    response = private_client.get(
        "/api/v1/health", headers={"Origin": "http://localhost:3100"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
