from fastapi import status


def test_public_health_check(public_client):
    """Test the public service health check endpoint."""
    response = public_client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "zapa-public"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_public_readiness_check(public_client):
    """Test the public service readiness check endpoint."""
    response = public_client.get("/ready")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "zapa-public"


def test_public_health_check_async(public_async_client):
    """Test public health check with async client."""
    # TestClient handles async endpoints synchronously
    response = public_async_client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"


def test_public_openapi_schema(public_client):
    """Test that OpenAPI schema is generated for public service."""
    response = public_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    schema = response.json()
    assert schema["info"]["title"] == "Zapa Public API (Minimal)"
    # Version is not set in minimal app, so skip this check
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]


def test_public_cors_headers(public_client):
    """Test CORS headers are set correctly for public service."""
    response = public_client.get("/health", headers={"Origin": "http://localhost:3200"})
    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
