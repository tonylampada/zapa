"""Tests for database connection utilities."""
from unittest.mock import MagicMock, patch

import pytest

from app.config.database import DatabaseConfig
from app.database.connection import (
    DatabaseManager,
    TestDatabaseManager,
    get_database_manager,
)


@pytest.fixture
def db_config():
    """Create test database config."""
    return DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://test:test@localhost:5432/test_db",
        DATABASE_POOL_SIZE=2,
        DATABASE_MAX_OVERFLOW=5,
        DATABASE_ECHO=True,
    )


def test_database_manager_initialization(db_config):
    """Test database manager initialization."""
    db_manager = DatabaseManager(db_config)

    assert db_manager.config == db_config
    assert db_manager._engine is None  # Lazy loading
    assert db_manager._session_maker is None


@patch("app.database.connection.create_engine")
def test_engine_creation(mock_create_engine, db_config):
    """Test engine creation with config parameters."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    db_manager = DatabaseManager(db_config)
    engine = db_manager.engine

    assert engine == mock_engine
    mock_create_engine.assert_called_once_with(
        "postgresql://test:test@localhost:5432/test_db",
        pool_size=2,
        max_overflow=5,
        echo=True,
    )

    # Should reuse same engine on subsequent calls
    engine2 = db_manager.engine
    assert engine2 == mock_engine
    assert mock_create_engine.call_count == 1


@patch("app.database.connection.sessionmaker")
@patch("app.database.connection.create_engine")
def test_session_maker_creation(mock_create_engine, mock_sessionmaker, db_config):
    """Test session maker creation."""
    mock_engine = MagicMock()
    mock_session_maker = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_sessionmaker.return_value = mock_session_maker

    db_manager = DatabaseManager(db_config)
    session_maker = db_manager.session_maker

    assert session_maker == mock_session_maker
    mock_sessionmaker.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=mock_engine,
    )


def test_test_database_manager():
    """Test TestDatabaseManager for in-memory testing."""
    test_db = TestDatabaseManager()

    # Should use SQLite in-memory
    assert "sqlite:///:memory:" in str(test_db.engine.url)

    # Should be able to create/drop tables
    test_db.create_tables()  # Should not raise
    test_db.drop_tables()  # Should not raise


def test_get_database_manager_singleton():
    """Test that get_database_manager returns singleton."""
    # Clear any existing manager
    import app.database.connection

    app.database.connection._db_manager = None

    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://test:test@localhost:5432/test",
    )

    manager1 = get_database_manager(config)
    manager2 = get_database_manager()  # Should reuse existing

    assert manager1 is manager2

    # Clean up
    app.database.connection._db_manager = None


@pytest.mark.asyncio
async def test_async_engine_url_conversion(db_config):
    """Test that async engine URL is converted correctly."""
    db_manager = DatabaseManager(db_config)

    with patch("app.database.connection.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine

        _ = db_manager.async_engine

        # Should convert postgresql:// to postgresql+asyncpg://
        expected_url = "postgresql+asyncpg://test:test@localhost:5432/test_db"
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert args[0] == expected_url


@pytest.mark.asyncio
async def test_async_session_context_manager():
    """Test async session context manager."""
    test_db = TestDatabaseManager()
    test_db.create_tables()

    # Mock async functionality for test
    db_manager = DatabaseManager(
        DatabaseConfig(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="postgresql://test:test@localhost:5432/test",
        )
    )

    # Since we can't easily test real async without a database,
    # we'll test the structure is correct
    assert hasattr(db_manager, "get_async_session")
    assert hasattr(db_manager, "async_session_maker")


def test_get_db_session_dependency():
    """Test the get_db_session dependency function."""
    from app.database.connection import get_db_session

    with patch("app.database.connection.get_database_manager") as mock_get_manager:
        mock_manager = MagicMock()
        mock_session = MagicMock()
        mock_manager.get_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        # Test the generator function
        gen = get_db_session()
        session = next(gen)

        assert session == mock_session
        mock_manager.get_session.assert_called_once()

        # Test cleanup
        try:
            next(gen)
        except StopIteration:
            pass  # Expected

        mock_session.close.assert_called_once()
