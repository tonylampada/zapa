"""Unit tests for public auth API endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.auth_code import AuthCode
from app.models.user import User
from app.public.api.v1.auth import (
    get_current_user_info,
    request_auth_code,
    verify_auth_code,
)
from app.schemas.auth import AuthCodeRequest, AuthCodeVerify


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_auth_service():
    """Create mock auth service."""
    mock = Mock()
    mock.check_rate_limit = Mock(return_value=True)
    mock.create_auth_code = Mock()
    mock.verify_auth_code = Mock()
    mock.create_access_token = Mock(return_value="test_token")
    return mock


@pytest.fixture
def mock_whatsapp_adapter():
    """Create mock WhatsApp adapter."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.get_sessions = AsyncMock(return_value=[{"id": "session1", "status": "active"}])
    mock.send_message = AsyncMock()
    return mock


@pytest.fixture
def test_user():
    """Create test user."""
    return User(
        id=1,
        phone_number="+1234567890",
        is_active=True,
        is_admin=False,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_auth_code():
    """Create test auth code."""
    return AuthCode(
        id=1,
        user_id=1,
        code="123456",
        used=False,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )


class TestAuthEndpoints:
    """Test cases for auth endpoints."""

    @pytest.mark.asyncio
    async def test_request_auth_code_success(
        self, mock_db, mock_auth_service, mock_whatsapp_adapter, test_user, test_auth_code
    ):
        """Test successful auth code request."""
        request = AuthCodeRequest(phone_number="+1234567890")

        # Setup mocks
        mock_auth_service.create_auth_code.return_value = (test_auth_code, False)

        # Call endpoint
        with patch("app.public.api.v1.auth.get_auth_service", return_value=mock_auth_service):
            with patch(
                "app.public.api.v1.auth.get_whatsapp_adapter", return_value=mock_whatsapp_adapter
            ):
                result = await request_auth_code(
                    request, mock_db, mock_auth_service, mock_whatsapp_adapter
                )

        # Verify result
        assert result["success"] is True
        assert result["message"] == "Authentication code sent via WhatsApp"
        assert result["phone_number"] == "+1234567890"

        # Verify mocks called
        mock_auth_service.check_rate_limit.assert_called_once_with(mock_db, "+1234567890")
        mock_auth_service.create_auth_code.assert_called_once_with(mock_db, "+1234567890")
        mock_whatsapp_adapter.get_sessions.assert_called_once()
        mock_whatsapp_adapter.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_auth_code_rate_limited(
        self, mock_db, mock_auth_service, mock_whatsapp_adapter
    ):
        """Test auth code request when rate limited."""
        request = AuthCodeRequest(phone_number="+1234567890")

        # Setup rate limit exceeded
        mock_auth_service.check_rate_limit.return_value = False

        # Call endpoint and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await request_auth_code(request, mock_db, mock_auth_service, mock_whatsapp_adapter)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_request_auth_code_whatsapp_failure(
        self, mock_db, mock_auth_service, mock_whatsapp_adapter, test_auth_code
    ):
        """Test auth code request when WhatsApp fails."""
        request = AuthCodeRequest(phone_number="+1234567890")

        # Setup mocks
        mock_auth_service.create_auth_code.return_value = (test_auth_code, False)
        mock_whatsapp_adapter.send_message.side_effect = Exception("WhatsApp error")

        # Call endpoint - should still succeed to prevent user enumeration
        result = await request_auth_code(request, mock_db, mock_auth_service, mock_whatsapp_adapter)

        assert result["success"] is True
        assert result["message"] == "Authentication code sent via WhatsApp"

    @pytest.mark.asyncio
    async def test_request_auth_code_no_sessions(
        self, mock_db, mock_auth_service, mock_whatsapp_adapter, test_auth_code
    ):
        """Test auth code request when no WhatsApp sessions available."""
        request = AuthCodeRequest(phone_number="+1234567890")

        # Setup mocks
        mock_auth_service.create_auth_code.return_value = (test_auth_code, False)
        mock_whatsapp_adapter.get_sessions.return_value = []  # No sessions

        # Call endpoint - should still succeed
        result = await request_auth_code(request, mock_db, mock_auth_service, mock_whatsapp_adapter)

        assert result["success"] is True
        assert result["message"] == "Authentication code sent via WhatsApp"
        mock_whatsapp_adapter.send_message.assert_not_called()  # Should not try to send

    @pytest.mark.asyncio
    async def test_verify_auth_code_success(self, mock_db, mock_auth_service, test_user):
        """Test successful auth code verification."""
        request = AuthCodeVerify(phone_number="+1234567890", code="123456")

        # Setup mocks
        mock_auth_service.verify_auth_code.return_value = test_user
        mock_auth_service.create_access_token.return_value = "test_jwt_token"

        # Call endpoint
        result = await verify_auth_code(request, mock_db, mock_auth_service)

        # Verify result
        assert result.access_token == "test_jwt_token"
        assert result.token_type == "bearer"
        assert result.expires_in == 86400
        assert result.user_id == test_user.id
        assert result.phone_number == test_user.phone_number

        # Verify mocks called
        mock_auth_service.verify_auth_code.assert_called_once_with(mock_db, "+1234567890", "123456")
        mock_auth_service.create_access_token.assert_called_once_with(
            user_id=test_user.id,
            phone_number=test_user.phone_number,
            is_admin=test_user.is_admin,
        )

    @pytest.mark.asyncio
    async def test_verify_auth_code_invalid(self, mock_db, mock_auth_service):
        """Test auth code verification with invalid code."""
        request = AuthCodeVerify(phone_number="+1234567890", code="999999")

        # Setup mocks
        mock_auth_service.verify_auth_code.return_value = None  # Invalid code

        # Call endpoint and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await verify_auth_code(request, mock_db, mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired code" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_info(self):
        """Test getting current user info."""
        current_user = {
            "user_id": 1,
            "phone_number": "+1234567890",
            "is_admin": False,
        }

        result = await get_current_user_info(current_user)

        assert result["user_id"] == 1
        assert result["phone_number"] == "+1234567890"
        assert result["is_authenticated"] is True

    def test_auth_code_request_validation(self):
        """Test auth code request validation."""
        # Valid phone numbers
        valid_numbers = [
            "+1234567890",
            "+12025551234",
            "+447911123456",
            "+33612345678",
        ]

        for number in valid_numbers:
            request = AuthCodeRequest(phone_number=number)
            assert request.phone_number == number

        # Invalid phone numbers
        invalid_numbers = [
            "1234567890",  # Missing +
            "+123",  # Too short
            "+123456789012345678",  # Too long
            "abc123",  # Non-numeric
            "",  # Empty
        ]

        for number in invalid_numbers:
            with pytest.raises(ValueError):
                AuthCodeRequest(phone_number=number)

    def test_auth_code_verify_validation(self):
        """Test auth code verify validation."""
        # Valid codes
        valid_codes = ["123456", "000000", "999999"]

        for code in valid_codes:
            request = AuthCodeVerify(phone_number="+1234567890", code=code)
            assert request.code == code

        # Invalid codes
        invalid_codes = [
            "12345",  # Too short
            "1234567",  # Too long
            "abcdef",  # Non-numeric
            "12 456",  # Contains space
            "",  # Empty
        ]

        for code in invalid_codes:
            with pytest.raises(ValueError):
                AuthCodeVerify(phone_number="+1234567890", code=code)
