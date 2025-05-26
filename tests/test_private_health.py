import pytest
from fastapi import status


def test_private_health_check(private_client):
    """Test the private service health check endpoint."""
    response = private_client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-private"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_private_readiness_check(private_client):
    """Test the private service readiness check endpoint."""
    response = private_client.get("/ready")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "zapa-private"


@pytest.mark.asyncio
async def test_private_health_check_async(private_async_client):
    """Test private health check with async client."""
    response = await private_async_client.get("/health")
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
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]


def test_private_cors_headers(private_client):
    """Test CORS headers are set correctly for private service."""
    response = private_client.get("/health", headers={"Origin": "http://localhost:3100"})
    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
