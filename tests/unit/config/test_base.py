"""Tests for base configuration."""

import pytest
from pydantic import ValidationError

from app.config.base import BaseSettings


def test_base_settings_default_values():
    """Test base settings with default values."""
    # Override environment variables set in conftest.py
    import os

    original_env = os.environ.get("ENVIRONMENT")
    if "ENVIRONMENT" in os.environ:
        del os.environ["ENVIRONMENT"]

    try:
        settings = BaseSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
        )

        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is True
        assert settings.LOG_LEVEL == "INFO"
        assert settings.API_V1_STR == "/api/v1"
        assert len(settings.CORS_ORIGINS) >= 2
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["ENVIRONMENT"] = original_env


def test_base_settings_validation():
    """Test base settings validation."""
    # Valid settings
    settings = BaseSettings(
        SECRET_KEY="very_long_secret_key_that_is_secure_123456789",
        ENCRYPTION_KEY="very_long_encryption_key_that_is_secure_123456789",
        ENVIRONMENT="production",
        DEBUG=False,
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False

    # Invalid secret key (too short)
    with pytest.raises(ValidationError) as exc_info:
        BaseSettings(
            SECRET_KEY="short",
            ENCRYPTION_KEY="b" * 32,
        )
    assert "at least 32 characters" in str(exc_info.value)

    # Invalid environment
    with pytest.raises(ValidationError):
        BaseSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            ENVIRONMENT="invalid",
        )


def test_cors_origins_parsing():
    """Test CORS origins parsing from string."""
    # String input
    settings = BaseSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        CORS_ORIGINS="http://localhost:3000,http://localhost:3100,https://example.com",
    )
    assert len(settings.CORS_ORIGINS) == 3
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "https://example.com" in settings.CORS_ORIGINS

    # List input
    settings = BaseSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        CORS_ORIGINS=["http://localhost:3000", "https://example.com"],
    )
    assert len(settings.CORS_ORIGINS) == 2


def test_environment_variable_loading(monkeypatch):
    """Test loading from environment variables."""
    monkeypatch.setenv("SECRET_KEY", "env_secret_key_" + "x" * 20)
    monkeypatch.setenv("ENCRYPTION_KEY", "env_encryption_key_" + "x" * 16)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = BaseSettings()

    assert settings.SECRET_KEY.startswith("env_secret_key_")
    assert settings.ENCRYPTION_KEY.startswith("env_encryption_key_")
    assert settings.ENVIRONMENT == "test"
    assert settings.DEBUG is False
    assert settings.LOG_LEVEL == "WARNING"
