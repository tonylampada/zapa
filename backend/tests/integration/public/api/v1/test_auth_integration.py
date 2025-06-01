"""Integration tests for public auth API endpoints."""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_auth_service
from app.core.database import get_db
from app.models.base import Base
from app.models.auth_code import AuthCode
from app.models.user import User
from app.public.main import app
from app.services.auth_service import AuthService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_db():
    """Create test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """Create test client."""
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    """Create database session for tests."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def mock_whatsapp():
    """Mock WhatsApp adapter for integration tests."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.get_sessions = AsyncMock(return_value=[{"id": "test_session", "status": "active"}])
    mock.send_message = AsyncMock()
    return mock


class TestAuthIntegration:
    """Integration tests for auth flow."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "zapa-public"

    @patch("app.public.api.v1.auth.get_whatsapp_adapter")
    def test_complete_auth_flow(self, mock_get_whatsapp, client, db_session, mock_whatsapp):
        """Test complete authentication flow from request to verify."""
        mock_get_whatsapp.return_value = mock_whatsapp
        phone_number = "+1234567890"

        # Step 1: Request auth code
        response = client.post("/api/v1/auth/request-code", json={"phone_number": phone_number})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Authentication code sent via WhatsApp"
        assert data["phone_number"] == phone_number

        # Verify auth code was created in database
        auth_code = (
            db_session.query(AuthCode).join(User).filter(User.phone_number == phone_number).first()
        )
        assert auth_code is not None
        assert len(auth_code.code) == 6
        assert auth_code.used is False

        # Step 2: Verify auth code
        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": phone_number, "code": auth_code.code}
        )

        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 86400
        assert token_data["phone_number"] == phone_number

        # Verify auth code was marked as used
        db_session.refresh(auth_code)
        assert auth_code.used is True

        # Step 3: Use token to access protected endpoint
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["phone_number"] == phone_number
        assert user_data["is_authenticated"] is True

    @patch("app.public.api.v1.auth.get_whatsapp_adapter")
    def test_auth_code_reuse_prevention(self, mock_get_whatsapp, client, db_session, mock_whatsapp):
        """Test that auth codes cannot be reused."""
        mock_get_whatsapp.return_value = mock_whatsapp
        phone_number = "+9876543210"

        # Request auth code
        response = client.post("/api/v1/auth/request-code", json={"phone_number": phone_number})
        assert response.status_code == 200

        # Get code from database
        auth_code = (
            db_session.query(AuthCode).join(User).filter(User.phone_number == phone_number).first()
        )
        code = auth_code.code

        # First verification should succeed
        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": phone_number, "code": code}
        )
        assert response.status_code == 200

        # Second verification with same code should fail
        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": phone_number, "code": code}
        )
        assert response.status_code == 401
        assert "Invalid or expired code" in response.json()["detail"]

    @patch("app.public.api.v1.auth.get_whatsapp_adapter")
    def test_rate_limiting(self, mock_get_whatsapp, client, db_session, mock_whatsapp):
        """Test rate limiting on auth code requests."""
        mock_get_whatsapp.return_value = mock_whatsapp
        phone_number = "+5555555555"

        # Make 3 requests (should all succeed)
        for i in range(3):
            response = client.post("/api/v1/auth/request-code", json={"phone_number": phone_number})
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.post("/api/v1/auth/request-code", json={"phone_number": phone_number})
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

    def test_invalid_phone_number_format(self, client):
        """Test validation of phone number format."""
        invalid_numbers = [
            "1234567890",  # Missing +
            "+123",  # Too short
            "abc123",  # Non-numeric
            "",  # Empty
        ]

        for number in invalid_numbers:
            response = client.post("/api/v1/auth/request-code", json={"phone_number": number})
            assert response.status_code == 422  # Validation error

    def test_invalid_auth_code_format(self, client):
        """Test validation of auth code format."""
        invalid_codes = [
            "12345",  # Too short
            "1234567",  # Too long
            "abcdef",  # Non-numeric
        ]

        for code in invalid_codes:
            response = client.post(
                "/api/v1/auth/verify", json={"phone_number": "+1234567890", "code": code}
            )
            assert response.status_code == 422  # Validation error

    def test_verify_with_wrong_code(self, client, db_session):
        """Test verification with wrong code."""
        # Create a user with an auth code
        user = User(
            phone_number="+1111111111",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.flush()

        auth_code = AuthCode(
            user_id=user.id,
            code="123456",
            used=False,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        db_session.add(auth_code)
        db_session.commit()

        # Try to verify with wrong code
        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": "+1111111111", "code": "999999"}
        )
        assert response.status_code == 401
        assert "Invalid or expired code" in response.json()["detail"]

    def test_verify_expired_code(self, client, db_session):
        """Test verification with expired code."""
        # Create a user with an expired auth code
        user = User(
            phone_number="+2222222222",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.flush()

        auth_code = AuthCode(
            user_id=user.id,
            code="654321",
            used=False,
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
        )
        db_session.add(auth_code)
        db_session.commit()

        # Try to verify expired code
        response = client.post(
            "/api/v1/auth/verify", json={"phone_number": "+2222222222", "code": "654321"}
        )
        assert response.status_code == 401
        assert "Invalid or expired code" in response.json()["detail"]

    def test_unauthorized_access_without_token(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # Forbidden

    def test_unauthorized_access_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token."""
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401  # Unauthorized


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_WHATSAPP", "false").lower() != "true",
    reason="WhatsApp integration tests disabled",
)
class TestWhatsAppIntegration:
    """Integration tests with real WhatsApp service."""

    def test_real_whatsapp_code_delivery(self, client):
        """Test actual WhatsApp code delivery."""
        test_phone = os.getenv("TEST_PHONE_NUMBER")
        if not test_phone:
            pytest.skip("TEST_PHONE_NUMBER not set")

        response = client.post("/api/v1/auth/request-code", json={"phone_number": test_phone})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # In a real test, you would need to:
        # 1. Check the WhatsApp message was received
        # 2. Extract the code from the message
        # 3. Use it to verify
        print(f"Auth code sent to {test_phone}. Check WhatsApp for verification.")
