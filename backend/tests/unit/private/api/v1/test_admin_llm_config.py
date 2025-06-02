import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import User, LLMConfig
from app.core.security import create_access_token


class TestAdminLLMConfigEndpoints:
    @pytest.fixture
    def admin_token(self):
        """Create a valid admin token."""
        return create_access_token(data={"sub": 1})

    @pytest.fixture
    def auth_headers(self, admin_token):
        """Create authorization headers."""
        return {"Authorization": f"Bearer {admin_token}"}

    def test_get_available_providers(self, private_client: TestClient, auth_headers):
        """Test getting list of available LLM providers."""
        response = private_client.get("/api/v1/admin/llm-config/providers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # OpenAI, Anthropic, Google

        # Check OpenAI provider
        openai_provider = next(p for p in data if p["provider"] == "openai")
        assert openai_provider["name"] == "OpenAI"
        assert "gpt-4" in openai_provider["models"]
        assert openai_provider["supports_function_calling"] is True

    def test_get_user_llm_config_success(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting user's LLM configuration."""
        # Create mock user and config
        user = User(id=1, phone_number="+1234567890")
        config = LLMConfig(
            id=1,
            user_id=1,
            provider="openai",
            model_settings={"model": "gpt-4", "api_key": "encrypted_key"},
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [user, config]

        response = private_client.get("/api/v1/admin/llm-config/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["provider"] == "openai"
        assert data["model_settings"]["api_key"] == "***hidden***"
        assert data["model_settings"]["model"] == "gpt-4"

    def test_get_user_llm_config_not_found(
        self, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test getting LLM config for user without config."""
        # Create mock user without config
        user = User(id=1, phone_number="+1234567890")

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [user, None]

        response = private_client.get("/api/v1/admin/llm-config/1", headers=auth_headers)

        assert response.status_code == 404
        assert "No LLM configuration found" in response.json()["detail"]

    @patch("app.private.api.v1.admin.llm_config.fernet")
    def test_create_user_llm_config_success(
        self, mock_fernet, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test creating LLM configuration for a user."""
        # Mock Fernet encryption
        mock_fernet.encrypt.return_value.decode.return_value = "encrypted_api_key"

        # Create mock user
        user = User(id=1, phone_number="+1234567890")

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = user
        mock_db.query.return_value.filter.return_value.update.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        config_data = {
            "provider": "openai",
            "api_key": "sk-test123",
            "model_settings": {"temperature": 0.7},
        }

        response = private_client.post(
            "/api/v1/admin/llm-config/1", json=config_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai"
        assert data["model_settings"]["api_key"] == "***hidden***"
        assert data["model_settings"]["model"] == "gpt-4"  # Default model

        # Verify config was added
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.private.api.v1.admin.llm_config.fernet")
    def test_update_user_llm_config_success(
        self, mock_fernet, private_client: TestClient, mock_db: Session, auth_headers
    ):
        """Test updating user's LLM configuration."""
        # Mock Fernet encryption
        mock_fernet.encrypt.return_value.decode.return_value = "new_encrypted_key"

        # Create mock config
        config = LLMConfig(
            id=1,
            user_id=1,
            provider="openai",
            model_settings={"model": "gpt-4", "api_key": "old_encrypted_key"},
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = config
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        update_data = {"api_key": "sk-new123", "model_settings": {"temperature": 0.9}}

        response = private_client.put(
            "/api/v1/admin/llm-config/1", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model_settings"]["api_key"] == "***hidden***"

        # Verify config was updated
        assert config.model_settings["api_key"] == "new_encrypted_key"
        assert config.model_settings["temperature"] == 0.9
        mock_db.commit.assert_called_once()

    @patch("app.private.api.v1.admin.llm_config.create_agent")
    @patch("app.private.api.v1.admin.llm_config.fernet")
    def test_test_user_llm_config_success(
        self,
        mock_fernet,
        mock_create_agent,
        private_client: TestClient,
        mock_db: Session,
        auth_headers,
    ):
        """Test testing user's LLM configuration."""
        # Mock Fernet decryption
        mock_fernet.decrypt.return_value.decode.return_value = "decrypted_api_key"

        # Mock agent
        mock_agent = Mock()
        mock_agent.run.return_value = "Hello, the LLM configuration is working!"
        mock_create_agent.return_value = mock_agent

        # Create mock user and config
        user = User(id=1, phone_number="+1234567890")
        config = LLMConfig(
            id=1,
            user_id=1,
            provider="openai",
            model_settings={"model": "gpt-4", "api_key": "encrypted_key"},
            is_active=True,
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [user, config]

        response = private_client.post("/api/v1/admin/llm-config/1/test", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["model_used"] == "gpt-4"
        assert data["response_time_ms"] > 0

        # Verify agent was created and called
        mock_create_agent.assert_called_once()
        mock_agent.run.assert_called_once()

    @patch("app.private.api.v1.admin.llm_config.create_agent")
    @patch("app.private.api.v1.admin.llm_config.fernet")
    def test_test_user_llm_config_failure(
        self,
        mock_fernet,
        mock_create_agent,
        private_client: TestClient,
        mock_db: Session,
        auth_headers,
    ):
        """Test testing user's LLM configuration with failure."""
        # Mock Fernet decryption
        mock_fernet.decrypt.return_value.decode.return_value = "decrypted_api_key"

        # Mock agent creation failure
        mock_create_agent.side_effect = Exception("Invalid API key")

        # Create mock user and config
        user = User(id=1, phone_number="+1234567890")
        config = LLMConfig(
            id=1,
            user_id=1,
            provider="openai",
            model_settings={"model": "gpt-4", "api_key": "encrypted_key"},
            is_active=True,
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [user, config]

        response = private_client.post("/api/v1/admin/llm-config/1/test", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error_message"] == "Invalid API key"
        assert data["model_used"] == "gpt-4"

    def test_llm_config_unauthorized(self, private_client: TestClient):
        """Test accessing LLM config endpoints without authentication."""
        # Test all endpoints
        endpoints = [
            ("/api/v1/admin/llm-config/providers", "get"),
            ("/api/v1/admin/llm-config/1", "get"),
            ("/api/v1/admin/llm-config/1", "post"),
            ("/api/v1/admin/llm-config/1", "put"),
            ("/api/v1/admin/llm-config/1/test", "post"),
        ]

        for endpoint, method in endpoints:
            if method == "get":
                response = private_client.get(endpoint)
            elif method == "post":
                response = private_client.post(endpoint, json={})
            elif method == "put":
                response = private_client.put(endpoint, json={})

            assert response.status_code == 401
