from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token


class TestAdminSystemEndpoints:
    @pytest.fixture
    def admin_token(self):
        """Create a valid admin token."""
        return create_access_token(data={"sub": 1})

    @pytest.fixture
    def auth_headers(self, admin_token):
        """Create authorization headers."""
        return {"Authorization": f"Bearer {admin_token}"}

    @patch("app.private.api.v1.admin.system.httpx.AsyncClient")
    @patch("app.private.api.v1.admin.system.psutil")
    def test_get_system_health_all_healthy(
        self, mock_psutil, mock_httpx, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting system health when all systems are healthy."""
        # Mock database connectivity
        mock_db.execute.return_value = None  # No exception means connected

        # Mock WhatsApp bridge health check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_async_client = MagicMock()
        mock_async_client.__aenter__.return_value.get.return_value = mock_response
        mock_httpx.return_value = mock_async_client

        # Mock system resource usage
        mock_psutil.virtual_memory.return_value.percent = 60.0
        mock_psutil.disk_usage.return_value.percent = 45.0
        mock_psutil.boot_time.return_value = 1000000.0

        # Mock time
        with patch("time.time", return_value=1100000.0):
            response = private_client.get("/api/v1/admin/system/health", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database_connected"] is True
        assert data["whatsapp_bridge_connected"] is True
        assert data["memory_usage_percent"] == 60.0
        assert data["disk_usage_percent"] == 45.0
        assert data["uptime_seconds"] == 100000

    @patch("app.private.api.v1.admin.system.httpx.AsyncClient")
    @patch("app.private.api.v1.admin.system.psutil")
    def test_get_system_health_degraded(
        self, mock_psutil, mock_httpx, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting system health when system is degraded."""
        # Mock database connectivity (working)
        mock_db.execute.return_value = None

        # Mock WhatsApp bridge health check (failing)
        mock_async_client = MagicMock()
        mock_async_client.__aenter__.return_value.get.side_effect = Exception("Connection error")
        mock_httpx.return_value = mock_async_client

        # Mock high memory usage
        mock_psutil.virtual_memory.return_value.percent = 92.0
        mock_psutil.disk_usage.return_value.percent = 50.0
        mock_psutil.boot_time.return_value = 1000000.0

        with patch("time.time", return_value=1100000.0):
            response = private_client.get("/api/v1/admin/system/health", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database_connected"] is True
        assert data["whatsapp_bridge_connected"] is False
        assert data["memory_usage_percent"] == 92.0

    @patch("app.private.api.v1.admin.system.psutil")
    def test_get_system_health_unhealthy(
        self, mock_psutil, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting system health when database is down."""
        # Mock database connectivity failure
        mock_db.execute.side_effect = Exception("Database connection failed")

        # Mock system resources
        mock_psutil.virtual_memory.return_value.percent = 50.0
        mock_psutil.disk_usage.return_value.percent = 40.0
        mock_psutil.boot_time.return_value = 1000000.0

        with patch("time.time", return_value=1100000.0):
            response = private_client.get("/api/v1/admin/system/health", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database_connected"] is False

    def test_get_system_stats_success(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting system statistics."""
        # Mock user counts
        mock_db.query.return_value.scalar.side_effect = [
            100,
            85,
            5000,
            150,
        ]  # total users, active users, total messages, messages today

        # Mock average response time
        mock_db.query.return_value.filter.return_value.scalar.return_value = None

        # Mock LLM provider usage
        provider_counts = [("openai", 50), ("anthropic", 30), ("google", 5)]
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = (
            provider_counts
        )

        response = private_client.get("/api/v1/admin/system/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 100
        assert data["active_users"] == 85
        assert data["total_messages"] == 5000
        assert data["messages_today"] == 150
        assert data["average_response_time_ms"] == 250.0  # Default value
        assert data["llm_provider_usage"]["openai"] == 50
        assert data["llm_provider_usage"]["anthropic"] == 30
        assert data["llm_provider_usage"]["google"] == 5

    def test_export_system_data_start(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test starting a system data export."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        response = private_client.post(
            "/api/v1/admin/system/export",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "include_messages": True,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "export_id" in data
        assert data["status"] == "pending"
        assert data["download_url"] is None
        assert data["error_message"] is None

    def test_export_system_data_invalid_dates(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test export with invalid date range."""
        # End date before start date
        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc) - timedelta(days=7)

        response = private_client.post(
            "/api/v1/admin/system/export",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]

        # Date range too large
        start_date = datetime.now(timezone.utc) - timedelta(days=400)
        end_date = datetime.now(timezone.utc)

        response = private_client.post(
            "/api/v1/admin/system/export",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "cannot exceed 365 days" in response.json()["detail"]

    @patch(
        "app.private.api.v1.admin.system.export_jobs",
        {
            "test-export-id": {
                "status": "completed",
                "download_url": "/download/test",
                "error_message": None,
            }
        },
    )
    def test_get_export_status_success(self, private_client: TestClient, auth_headers):
        """Test getting export job status."""
        response = private_client.get(
            "/api/v1/admin/system/export/test-export-id", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["export_id"] == "test-export-id"
        assert data["status"] == "completed"
        assert data["download_url"] == "/download/test"
        assert data["error_message"] is None

    def test_get_export_status_not_found(self, private_client: TestClient, auth_headers):
        """Test getting status of non-existent export job."""
        response = private_client.get(
            "/api/v1/admin/system/export/non-existent", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Export job not found" in response.json()["detail"]

    def test_system_endpoints_unauthorized(self, private_client: TestClient):
        """Test accessing system endpoints without authentication."""
        # Test all endpoints
        endpoints = [
            ("/api/v1/admin/system/health", "get"),
            ("/api/v1/admin/system/stats", "get"),
            ("/api/v1/admin/system/export", "post"),
            ("/api/v1/admin/system/export/123", "get"),
        ]

        for endpoint, method in endpoints:
            if method == "get":
                response = private_client.get(endpoint)
            elif method == "post":
                response = private_client.post(
                    endpoint, params={"start_date": "2024-01-01", "end_date": "2024-01-02"}
                )

            assert response.status_code == 401
