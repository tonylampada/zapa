"""Tests for public entrypoint configuration."""
import pytest
from pydantic import ValidationError

from app.config.public import PublicSettings


def test_public_service_settings_defaults():
    """Test public service settings with required values only."""
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="d" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )

    assert settings.SERVICE_NAME == "zapa-public"
    assert settings.VERSION == "0.1.0"
    assert settings.AUTH_CODE_LENGTH == 6
    assert settings.AUTH_CODE_EXPIRE_MINUTES == 5
    assert settings.JWT_TOKEN_EXPIRE_HOURS == 24
    assert settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert settings.PRIVATE_SERVICE_URL == "http://localhost:8001"


def test_cors_origins_includes_public_frontend():
    """Test that CORS origins include public frontend by default."""
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="d" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )

    assert "http://localhost:3200" in settings.CORS_ORIGINS

    # Test with custom origins
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="d" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        CORS_ORIGINS="https://app.example.com,https://www.example.com",
    )

    # Should still include public frontend
    assert "http://localhost:3200" in settings.CORS_ORIGINS
    assert "https://app.example.com" in settings.CORS_ORIGINS
    assert "https://www.example.com" in settings.CORS_ORIGINS


def test_rate_limiting_validation():
    """Test rate limiting configuration validation."""
    # Valid settings
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="d" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        AUTH_RATE_LIMIT_PER_HOUR=50,
        API_RATE_LIMIT_PER_MINUTE=200,
    )

    assert settings.AUTH_RATE_LIMIT_PER_HOUR == 50
    assert settings.API_RATE_LIMIT_PER_MINUTE == 200

    # Invalid rate limit (too high)
    with pytest.raises(ValidationError):
        PublicSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            PRIVATE_SERVICE_SECRET="d" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            AUTH_RATE_LIMIT_PER_HOUR=200,  # Max is 100
        )


def test_data_access_limits():
    """Test data access limit configuration."""
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="d" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        MAX_MESSAGES_PER_REQUEST=500,
        MAX_SEARCH_RESULTS=100,
        MESSAGE_HISTORY_DAYS=730,
    )

    assert settings.MAX_MESSAGES_PER_REQUEST == 500
    assert settings.MAX_SEARCH_RESULTS == 100
    assert settings.MESSAGE_HISTORY_DAYS == 730

    # Test boundaries
    with pytest.raises(ValidationError):
        PublicSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            PRIVATE_SERVICE_SECRET="d" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            MAX_MESSAGES_PER_REQUEST=2000,  # Max is 1000
        )


def test_private_service_communication():
    """Test private service communication settings."""
    settings = PublicSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        PRIVATE_SERVICE_SECRET="shared_secret_for_service_auth_123456789",
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        PRIVATE_SERVICE_URL="http://private-api:8001",
        PRIVATE_SERVICE_TIMEOUT=30.0,
    )

    assert settings.PRIVATE_SERVICE_URL == "http://private-api:8001"
    assert settings.PRIVATE_SERVICE_TIMEOUT == 30.0
    assert len(settings.PRIVATE_SERVICE_SECRET) >= 32