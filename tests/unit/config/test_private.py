"""Tests for private entrypoint configuration."""
import pytest
from pydantic import ValidationError

from app.config.private import PrivateSettings


def test_private_service_settings_defaults():
    """Test private service settings with required values only."""
    settings = PrivateSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )

    assert settings.SERVICE_NAME == "zapa-private"
    assert settings.VERSION == "0.1.0"
    assert settings.WHATSAPP_BRIDGE_URL == "http://localhost:3000"
    assert settings.WHATSAPP_BRIDGE_TIMEOUT == 30.0
    assert settings.ADMIN_TOKEN_EXPIRE_MINUTES == 60 * 24
    assert settings.RATE_LIMIT_ENABLED is True


def test_webhook_url_property():
    """Test webhook URL property construction."""
    settings = PrivateSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        WEBHOOK_BASE_URL="https://api.example.com",
    )

    expected = "https://api.example.com/api/v1/webhooks/whatsapp"
    assert settings.webhook_url == expected

    # Test with trailing slash
    settings.WEBHOOK_BASE_URL = "https://api.example.com/"
    expected = "https://api.example.com/api/v1/webhooks/whatsapp"
    assert settings.webhook_url == expected


def test_integration_test_flags():
    """Test integration test flag defaults."""
    settings = PrivateSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )

    assert settings.INTEGRATION_TEST_WHATSAPP is False
    assert settings.INTEGRATION_TEST_OPENAI is False
    assert settings.INTEGRATION_TEST_ANTHROPIC is False
    assert settings.INTEGRATION_TEST_GOOGLE is False


def test_validation_errors():
    """Test validation errors for private service settings."""
    # Missing required field
    import os

    # Remove environment variable temporarily
    original_admin_secret = os.environ.get("ADMIN_TOKEN_SECRET")
    if "ADMIN_TOKEN_SECRET" in os.environ:
        del os.environ["ADMIN_TOKEN_SECRET"]

    try:
        with pytest.raises(ValidationError):
            PrivateSettings(
                SECRET_KEY="a" * 32,
                ENCRYPTION_KEY="b" * 32,
                # Missing ADMIN_TOKEN_SECRET
                DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            )
    finally:
        # Restore original environment
        if original_admin_secret is not None:
            os.environ["ADMIN_TOKEN_SECRET"] = original_admin_secret

    # Invalid timeout range
    with pytest.raises(ValidationError):
        PrivateSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            ADMIN_TOKEN_SECRET="c" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            WHATSAPP_BRIDGE_TIMEOUT=400.0,  # Too high
        )