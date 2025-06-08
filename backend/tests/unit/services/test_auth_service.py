"""Unit tests for the authentication service."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from jose import jwt
from sqlalchemy.orm import Session

from app.models.auth_code import AuthCode
from app.models.user import User
from app.services.auth_service import AuthService


@pytest.fixture
def auth_service():
    """Create auth service instance."""
    return AuthService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock(spec=Session)


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


class TestAuthService:
    """Test cases for AuthService."""

    def test_generate_auth_code(self, auth_service):
        """Test auth code generation."""
        code = auth_service.generate_auth_code()

        assert len(code) == 6
        assert code.isdigit()

        # Generate multiple codes and ensure they're different
        codes = [auth_service.generate_auth_code() for _ in range(10)]
        assert len(set(codes)) > 5  # Should have high uniqueness

    def test_create_auth_code_new_user(self, auth_service, mock_db):
        """Test creating auth code for new user."""
        phone_number = "+1234567890"

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.update.return_value = None

        # Call create_auth_code
        auth_code, is_new_user = auth_service.create_auth_code(mock_db, phone_number)

        # Verify new user was created
        assert is_new_user is True
        assert mock_db.add.call_count == 2  # User and AuthCode
        assert mock_db.commit.called

        # Verify auth code properties
        assert isinstance(auth_code, AuthCode)
        assert len(auth_code.code) == 6
        assert auth_code.used is False
        assert auth_code.expires_at > datetime.utcnow()

    def test_create_auth_code_existing_user(self, auth_service, mock_db, test_user):
        """Test creating auth code for existing user."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = test_user
        mock_db.query.return_value.filter.return_value.update.return_value = None

        # Call create_auth_code
        auth_code, is_new_user = auth_service.create_auth_code(
            mock_db, test_user.phone_number, test_user
        )

        # Verify existing user was used
        assert is_new_user is False
        assert mock_db.add.call_count == 1  # Only AuthCode
        assert mock_db.commit.called

        # Verify auth code properties
        assert isinstance(auth_code, AuthCode)
        assert auth_code.user_id == test_user.id

    def test_verify_auth_code_success(self, auth_service, mock_db, test_user):
        """Test successful auth code verification."""
        code = "123456"
        valid_auth_code = AuthCode(
            id=1,
            user_id=test_user.id,
            code=code,
            used=False,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            test_user,  # User query
            valid_auth_code,  # AuthCode query
        ]

        # Verify code
        result = auth_service.verify_auth_code(mock_db, test_user.phone_number, code)

        assert result == test_user
        assert valid_auth_code.used is True
        assert mock_db.commit.called

    def test_verify_auth_code_invalid(self, auth_service, mock_db, test_user):
        """Test invalid auth code verification."""
        # Test non-existent user
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = auth_service.verify_auth_code(mock_db, "+9999999999", "123456")
        assert result is None

        # Test non-existent code
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            test_user,  # User exists
            None,  # Code doesn't exist
        ]
        result = auth_service.verify_auth_code(
            mock_db, test_user.phone_number, "999999"
        )
        assert result is None

    def test_verify_auth_code_expired(self, auth_service, mock_db, test_user):
        """Test expired auth code verification."""
        AuthCode(
            id=1,
            user_id=test_user.id,
            code="123456",
            used=False,
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
        )

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            test_user,
            None,  # Query won't return expired codes
        ]

        result = auth_service.verify_auth_code(
            mock_db, test_user.phone_number, "123456"
        )
        assert result is None

    def test_create_access_token(self, auth_service):
        """Test JWT token creation."""
        user_id = 1
        phone_number = "+1234567890"
        is_admin = False

        token = auth_service.create_access_token(user_id, phone_number, is_admin)

        # Decode token to verify contents
        decoded = jwt.decode(
            token, auth_service.secret_key, algorithms=[auth_service.algorithm]
        )

        assert decoded["user_id"] == user_id
        assert decoded["phone_number"] == phone_number
        assert decoded["is_admin"] == is_admin
        assert "exp" in decoded
        assert decoded["sub"] == str(user_id)

    def test_verify_access_token_success(self, auth_service):
        """Test successful token verification."""
        # Create a valid token
        token = auth_service.create_access_token(1, "+1234567890", False)

        # Verify it
        payload = auth_service.verify_access_token(token)

        assert payload["user_id"] == 1
        assert payload["phone_number"] == "+1234567890"
        assert payload["is_admin"] is False

    def test_verify_access_token_invalid(self, auth_service):
        """Test invalid token verification."""
        with pytest.raises(ValueError, match="Invalid token"):
            auth_service.verify_access_token("invalid.token.here")

    def test_verify_access_token_expired(self, auth_service):
        """Test expired token verification."""
        # Create an expired token
        expires_delta = timedelta(seconds=-1)  # Already expired
        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": "1",
            "user_id": 1,
            "phone_number": "+1234567890",
            "is_admin": False,
            "exp": expire,
        }
        expired_token = jwt.encode(
            to_encode, auth_service.secret_key, algorithm=auth_service.algorithm
        )

        with pytest.raises(ValueError, match="Invalid token"):
            auth_service.verify_access_token(expired_token)

    def test_check_rate_limit_new_user(self, auth_service, mock_db):
        """Test rate limit check for new user."""
        # Mock no user found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = auth_service.check_rate_limit(mock_db, "+9999999999")
        assert result is True  # New users can always request

    def test_check_rate_limit_within_limit(self, auth_service, mock_db, test_user):
        """Test rate limit check within limit."""
        # Mock user found and count under limit
        mock_db.query.return_value.filter.return_value.first.return_value = test_user
        mock_db.query.return_value.filter.return_value.count.return_value = (
            2  # Under limit of 3
        )

        result = auth_service.check_rate_limit(mock_db, test_user.phone_number)
        assert result is True

    def test_check_rate_limit_exceeded(self, auth_service, mock_db, test_user):
        """Test rate limit check when exceeded."""
        # Mock user found and count at limit
        mock_db.query.return_value.filter.return_value.first.return_value = test_user
        mock_db.query.return_value.filter.return_value.count.return_value = (
            3  # At limit
        )

        result = auth_service.check_rate_limit(mock_db, test_user.phone_number)
        assert result is False
