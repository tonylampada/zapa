from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Message, User


class TestAdminUsersEndpoints:
    @pytest.fixture
    def admin_token(self):
        """Create a valid admin token."""
        return create_access_token(data={"sub": 1})

    @pytest.fixture
    def auth_headers(self, admin_token):
        """Create authorization headers."""
        return {"Authorization": f"Bearer {admin_token}"}

    def test_list_users_success(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test listing users with pagination."""
        # Create mock users
        users = [
            User(
                id=i,
                phone_number=f"+123456789{i}",
                first_name=f"User{i}",
                last_name="Test",
                is_active=True,
                first_seen=datetime.utcnow(),
            )
            for i in range(1, 4)
        ]

        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value.limit.return_value.all.return_value = users
        mock_db.query.return_value = mock_query

        # Mock message count queries
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        response = private_client.get("/api/v1/admin/users/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["users"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_users_with_search(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test listing users with search filter."""
        # Create mock user matching search
        user = User(
            id=1,
            phone_number="+1234567890",
            first_name="John",
            last_name="Doe",
            is_active=True,
            first_seen=datetime.utcnow(),
        )

        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [user]
        mock_db.query.return_value = mock_query

        # Mock message count queries
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        response = private_client.get("/api/v1/admin/users/?search=john", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["users"]) == 1

    def test_list_users_unauthorized(self, private_client: TestClient):
        """Test listing users without authentication."""
        response = private_client.get("/api/v1/admin/users/")
        assert response.status_code == 401

    def test_get_user_success(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test getting a specific user."""
        # Create mock user
        user = User(
            id=1,
            phone_number="+1234567890",
            first_name="John",
            last_name="Doe",
            is_active=True,
            first_seen=datetime.utcnow(),
            user_metadata={"key": "value"},
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user

        # Mock message counts
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            10,
            5,
        ]  # sent, received

        # Mock LLM config check
        mock_db.query.return_value.filter.return_value.first.return_value = Mock()  # Has config

        response = private_client.get("/api/v1/admin/users/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["phone_number"] == "+1234567890"
        assert data["llm_config_set"] is True
        assert data["messages_sent"] == 10
        assert data["messages_received"] == 5

    def test_get_user_not_found(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test getting a non-existent user."""
        # Mock database query to return None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = private_client.get("/api/v1/admin/users/999", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_create_user_success(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test creating a new user."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing user
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        user_data = {
            "phone_number": "+1234567890",
            "first_name": "John",
            "last_name": "Doe",
            "is_active": True,
        }

        response = private_client.post("/api/v1/admin/users/", json=user_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+1234567890"
        assert data["first_name"] == "John"

        # Verify user was added to database
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_user_already_exists(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test creating a user that already exists."""
        # Mock existing user
        existing_user = User(id=1, phone_number="+1234567890")
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        user_data = {"phone_number": "+1234567890", "first_name": "John"}

        response = private_client.post("/api/v1/admin/users/", json=user_data, headers=auth_headers)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_update_user_success(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test updating a user."""
        # Create mock user
        user = User(
            id=1,
            phone_number="+1234567890",
            first_name="John",
            last_name="Doe",
            is_active=True,
            first_seen=datetime.utcnow(),
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock message counts for response
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [5, 3]

        update_data = {"first_name": "Jane", "is_active": False}

        response = private_client.put(
            "/api/v1/admin/users/1", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

        # Verify user was updated
        assert user.first_name == "Jane"
        assert user.is_active is False
        mock_db.commit.assert_called_once()

    def test_delete_user_success(self, private_client: TestClient, mock_db: Session, auth_headers):
        """Test deleting a user."""
        # Create mock user (non-admin)
        user = User(id=1, phone_number="+1234567890", is_admin=False)

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        response = private_client.delete("/api/v1/admin/users/1", headers=auth_headers)

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify user was deleted
        mock_db.delete.assert_called_once_with(user)
        mock_db.commit.assert_called_once()

    def test_delete_admin_user_forbidden(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test that admin users cannot be deleted."""
        # Create mock admin user
        admin_user = User(id=1, phone_number="admin", is_admin=True)

        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = admin_user

        response = private_client.delete("/api/v1/admin/users/1", headers=auth_headers)

        assert response.status_code == 400
        assert "Cannot delete admin users" in response.json()["detail"]

    def test_get_user_conversations_success(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting user conversation history."""
        # Create mock user and messages
        user = User(id=1, phone_number="+1234567890")
        messages = [
            Message(
                id=i,
                user_id=1,
                content=f"Message {i}",
                is_from_user=i % 2 == 0,
                message_type="text",
                status="sent",
                created_at=datetime.utcnow(),
            )
            for i in range(1, 4)
        ]

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = (
            messages
        )
        mock_db.query.return_value = mock_query

        response = private_client.get("/api/v1/admin/users/1/conversations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["messages"]) == 3

    def test_clear_user_conversations_success(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test clearing user conversation history."""
        # Create mock user
        user = User(id=1, phone_number="+1234567890")

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user
        mock_db.query.return_value.filter.return_value.delete.return_value = 10
        mock_db.commit = Mock()

        response = private_client.delete(
            "/api/v1/admin/users/1/conversations", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Deleted 10 messages"
        mock_db.commit.assert_called_once()
