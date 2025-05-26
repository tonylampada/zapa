"""Tests for core exception classes."""
import pytest

from app.core.exceptions import (
    ZapaException,
    DatabaseError,
    ConfigurationError,
    WhatsAppBridgeError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    RateLimitError,
    ExternalServiceError,
)


def test_zapa_exception_basic():
    """Test basic ZapaException functionality."""
    exc = ZapaException("Test message")

    assert exc.message == "Test message"
    assert exc.error_code == "ZAPA_ERROR"
    assert exc.status_code == 500
    assert exc.details == {}
    assert str(exc) == "Test message"


def test_zapa_exception_with_details():
    """Test ZapaException with custom details."""
    details = {"field": "email", "reason": "invalid"}
    exc = ZapaException(
        message="Custom error",
        error_code="CUSTOM_ERROR",
        status_code=400,
        details=details,
    )

    assert exc.message == "Custom error"
    assert exc.error_code == "CUSTOM_ERROR"
    assert exc.status_code == 400
    assert exc.details == details


def test_database_error():
    """Test DatabaseError exception."""
    exc = DatabaseError("Connection failed")

    assert exc.message == "Connection failed"
    assert exc.error_code == "DATABASE_ERROR"
    assert exc.status_code == 500


def test_configuration_error():
    """Test ConfigurationError exception."""
    exc = ConfigurationError("Missing config key")

    assert exc.message == "Missing config key"
    assert exc.error_code == "CONFIGURATION_ERROR"
    assert exc.status_code == 500


def test_whatsapp_bridge_error():
    """Test WhatsAppBridgeError exception."""
    exc = WhatsAppBridgeError("Bridge unavailable")

    assert exc.message == "Bridge unavailable"
    assert exc.error_code == "WHATSAPP_BRIDGE_ERROR"
    assert exc.status_code == 503


def test_authentication_error():
    """Test AuthenticationError exception."""
    exc = AuthenticationError()

    assert exc.message == "Authentication failed"
    assert exc.error_code == "AUTHENTICATION_ERROR"
    assert exc.status_code == 401

    # With custom message
    exc_custom = AuthenticationError("Invalid token")
    assert exc_custom.message == "Invalid token"


def test_authorization_error():
    """Test AuthorizationError exception."""
    exc = AuthorizationError()

    assert exc.message == "Access denied"
    assert exc.error_code == "AUTHORIZATION_ERROR"
    assert exc.status_code == 403


def test_validation_error():
    """Test ValidationError exception."""
    exc = ValidationError("Invalid email format", field="email")

    assert exc.message == "Invalid email format"
    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.status_code == 422
    assert exc.details["field"] == "email"


def test_validation_error_without_field():
    """Test ValidationError without specific field."""
    exc = ValidationError("General validation error")

    assert exc.message == "General validation error"
    assert "field" not in exc.details


def test_not_found_error():
    """Test NotFoundError exception."""
    exc = NotFoundError("User", "123")

    assert exc.message == "User not found: 123"
    assert exc.error_code == "NOT_FOUND"
    assert exc.status_code == 404
    assert exc.details["resource"] == "User"
    assert exc.details["identifier"] == "123"


def test_not_found_error_without_identifier():
    """Test NotFoundError without identifier."""
    exc = NotFoundError("Session")

    assert exc.message == "Session not found"
    assert exc.details["resource"] == "Session"
    assert "identifier" not in exc.details


def test_rate_limit_error():
    """Test RateLimitError exception."""
    exc = RateLimitError()

    assert exc.message == "Rate limit exceeded"
    assert exc.error_code == "RATE_LIMIT_EXCEEDED"
    assert exc.status_code == 429


def test_external_service_error():
    """Test ExternalServiceError exception."""
    exc = ExternalServiceError("OpenAI", "API quota exceeded")

    assert exc.message == "OpenAI: API quota exceeded"
    assert exc.error_code == "EXTERNAL_SERVICE_ERROR"
    assert exc.status_code == 502
    assert exc.details["service"] == "OpenAI"
