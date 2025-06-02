import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.admin import AdminLogin, AdminTokenResponse


class TestAuthEndpoints:
    def test_admin_login_success(self, private_client: TestClient, mock_db: Session):
        """Test successful admin login."""
        # Create mock admin user
        admin_user = User(
            id=1,
            phone_number="admin",
            display_name="System Admin",
            first_name="System",
            last_name="Admin",
            is_admin=True,
            is_active=True,
        )

        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = admin_user
        mock_db.query.return_value = mock_query

        # Make login request
        response = private_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_admin_login_invalid_credentials(self, private_client: TestClient, mock_db: Session):
        """Test login with invalid credentials."""
        # Mock database query to return no user
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        # Make login request with wrong credentials
        response = private_client.post(
            "/api/v1/auth/login", json={"username": "wrong", "password": "wrong"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_admin_login_creates_first_admin(self, private_client: TestClient, mock_db: Session):
        """Test that first admin user is created if none exists."""
        # Mock database query to simulate no admin exists
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [None, None]  # No user, then no admin
        mock_db.query.return_value = mock_query

        # Mock the database add and commit
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Make login request with default admin credentials
        response = private_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        # Verify admin user was created
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_admin_login_validation_error(self, private_client: TestClient):
        """Test login with invalid request data."""
        # Missing password
        response = private_client.post("/api/v1/auth/login", json={"username": "admin"})

        assert response.status_code == 422

        # Short username
        response = private_client.post(
            "/api/v1/auth/login", json={"username": "ab", "password": "admin123"}
        )

        assert response.status_code == 422

        # Short password
        response = private_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "123"}
        )

        assert response.status_code == 422
