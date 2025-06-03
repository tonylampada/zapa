"""Tests for database configuration."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.config.database import DatabaseConfig


def test_database_config_valid():
    """Test valid database configuration."""
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        REDIS_URL="redis://localhost:6379/1",
    )

    assert config.DATABASE_URL.startswith("postgresql://")
    assert config.DATABASE_POOL_SIZE == 5
    assert config.DATABASE_MAX_OVERFLOW == 10
    assert config.REDIS_URL.startswith("redis://")
    assert config.REDIS_KEY_PREFIX == "zapa:"


def test_database_url_validation():
    """Test database URL validation."""
    # Valid PostgreSQL URL
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/zapa",
    )
    assert config.DATABASE_URL.startswith("postgresql+psycopg2://")

    # Invalid database URL
    with pytest.raises(ValidationError) as exc_info:
        DatabaseConfig(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="mysql://user:pass@localhost:3306/db",
        )
    assert "PostgreSQL URL" in str(exc_info.value)


def test_redis_url_validation():
    """Test Redis URL validation."""
    # Valid Redis URL
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        REDIS_URL="redis://localhost:6379/0",
    )
    assert config.REDIS_URL == "redis://localhost:6379/0"

    # Invalid Redis URL
    with pytest.raises(ValidationError):
        DatabaseConfig(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            REDIS_URL="http://localhost:6379",
        )


@patch("app.config.database.create_engine")
def test_get_database_engine(mock_create_engine):
    """Test database engine creation."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        DATABASE_POOL_SIZE=10,
        DATABASE_MAX_OVERFLOW=20,
        DATABASE_ECHO=True,
    )

    engine = config.get_database_engine()

    assert engine == mock_engine
    mock_create_engine.assert_called_once_with(
        "postgresql://user:pass@localhost:5432/zapa",
        pool_size=10,
        max_overflow=20,
        echo=True,
    )


@patch("app.config.database.sessionmaker")
@patch("app.config.database.create_engine")
def test_get_session_maker(mock_create_engine, mock_sessionmaker):
    """Test session maker creation."""
    mock_engine = MagicMock()
    mock_session_maker = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_sessionmaker.return_value = mock_session_maker

    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )

    session_maker = config.get_session_maker()

    assert session_maker == mock_session_maker
    mock_sessionmaker.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=mock_engine,
    )
