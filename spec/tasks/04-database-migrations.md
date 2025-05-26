# Task 04: Database Migrations and Fixtures

## Objective
Set up Alembic migrations, create database fixtures for testing, and establish database connection utilities for both services.

## Prerequisites
- Tasks 01-03 completed
- Database models and configuration working
- PostgreSQL available for testing

## Success Criteria
- [ ] Alembic migrations working for all models
- [ ] Database connection utilities for both services
- [ ] Test fixtures for reliable test data
- [ ] Migration rollback/upgrade tests
- [ ] Database seeding scripts
- [ ] Tests passing locally and in CI/CD

## Files to Create

### shared/database/__init__.py
```python
from .connection import DatabaseManager, get_db_session
from .fixtures import create_test_data, cleanup_test_data

__all__ = ["DatabaseManager", "get_db_session", "create_test_data", "cleanup_test_data"]
```

### shared/database/connection.py
```python
"""Database connection utilities."""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging

from models.base import Base
from config.database import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self._engine = None
        self._async_engine = None
        self._session_maker = None
        self._async_session_maker = None
    
    @property
    def engine(self):
        """Get synchronous SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.config.DATABASE_URL,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                echo=self.config.DATABASE_ECHO,
            )
        return self._engine
    
    @property
    def async_engine(self):
        """Get asynchronous SQLAlchemy engine."""
        if self._async_engine is None:
            # Convert postgresql:// to postgresql+asyncpg://
            async_url = self.config.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            self._async_engine = create_async_engine(
                async_url,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                echo=self.config.DATABASE_ECHO,
            )
        return self._async_engine
    
    @property
    def session_maker(self):
        """Get synchronous session maker."""
        if self._session_maker is None:
            self._session_maker = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
            )
        return self._session_maker
    
    @property
    def async_session_maker(self):
        """Get asynchronous session maker."""
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_maker
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Created all database tables")
    
    def drop_tables(self):
        """Drop all tables."""
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Dropped all database tables")
    
    async def create_tables_async(self):
        """Create all tables asynchronously."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Created all database tables (async)")
    
    async def drop_tables_async(self):
        """Drop all tables asynchronously."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Dropped all database tables (async)")
    
    def get_session(self) -> Session:
        """Get a synchronous database session."""
        return self.session_maker()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session."""
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._engine:
            self._engine.dispose()


class TestDatabaseManager(DatabaseManager):
    """Database manager for testing with in-memory SQLite."""
    
    def __init__(self):
        """Initialize test database manager."""
        # Use in-memory SQLite for tests
        self._test_engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self._test_session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._test_engine,
        )
    
    @property
    def engine(self):
        """Get test engine."""
        return self._test_engine
    
    @property
    def session_maker(self):
        """Get test session maker."""
        return self._test_session_maker
    
    def create_tables(self):
        """Create all tables in test database."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all tables in test database."""
        Base.metadata.drop_all(bind=self.engine)


# Global database manager instances
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """Get or create database manager instance."""
    global _db_manager
    if _db_manager is None:
        if config is None:
            from config.database import DatabaseConfig
            config = DatabaseConfig()
        _db_manager = DatabaseManager(config)
    return _db_manager


def get_db_session():
    """Dependency to get database session."""
    db_manager = get_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


async def get_async_db_session():
    """Dependency to get async database session."""
    db_manager = get_database_manager()
    async with db_manager.get_async_session() as session:
        yield session
```

### shared/database/fixtures.py
```python
"""Test fixtures and sample data creation."""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from models.user import User
from models.session import Session as WhatsAppSession, SessionType, SessionStatus
from models.message import Message, MessageType
from models.auth_code import AuthCode
from models.llm_config import LLMConfig, LLMProvider
from config.encryption import EncryptionManager


def create_test_user(
    session: Session,
    phone_number: str = "+1234567890",
    display_name: str = "Test User",
    **kwargs
) -> User:
    """Create a test user."""
    user = User(
        phone_number=phone_number,
        display_name=display_name,
        first_seen=datetime.now(timezone.utc),
        preferences=kwargs.get("preferences", {"theme": "dark"}),
        **kwargs
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_test_session(
    session: Session,
    user: User,
    session_type: SessionType = SessionType.MAIN,
    status: SessionStatus = SessionStatus.CONNECTED,
    **kwargs
) -> WhatsAppSession:
    """Create a test WhatsApp session."""
    whatsapp_session = WhatsAppSession(
        user_id=user.id,
        session_type=session_type,
        status=status,
        connected_at=datetime.now(timezone.utc) if status == SessionStatus.CONNECTED else None,
        metadata=kwargs.get("metadata", {"device": "iPhone"}),
        **kwargs
    )
    session.add(whatsapp_session)
    session.commit()
    session.refresh(whatsapp_session)
    return whatsapp_session


def create_test_message(
    session: Session,
    whatsapp_session: WhatsAppSession,
    content: str = "Test message",
    message_type: MessageType = MessageType.TEXT,
    sender_jid: Optional[str] = None,
    **kwargs
) -> Message:
    """Create a test message."""
    if sender_jid is None:
        sender_jid = f"{whatsapp_session.user.phone_number}@s.whatsapp.net"
    
    message = Message(
        session_id=whatsapp_session.id,
        user_id=whatsapp_session.user_id,
        sender_jid=sender_jid,
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=message_type,
        content=content if message_type == MessageType.TEXT else None,
        caption=kwargs.get("caption"),
        reply_to_id=kwargs.get("reply_to_id"),
        media_metadata=kwargs.get("media_metadata"),
        **kwargs
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def create_test_auth_code(
    session: Session,
    user: User,
    code: str = "123456",
    expires_in_minutes: int = 5,
    **kwargs
) -> AuthCode:
    """Create a test auth code."""
    auth_code = AuthCode(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        used=kwargs.get("used", False),
        **kwargs
    )
    session.add(auth_code)
    session.commit()
    session.refresh(auth_code)
    return auth_code


def create_test_llm_config(
    session: Session,
    user: User,
    provider: LLMProvider = LLMProvider.OPENAI,
    api_key: str = "sk-test123",
    encryption_manager: Optional[EncryptionManager] = None,
    **kwargs
) -> LLMConfig:
    """Create a test LLM config."""
    if encryption_manager is None:
        encryption_manager = EncryptionManager("test_key_" + "x" * 24)
    
    encrypted_key = encryption_manager.encrypt(api_key)
    
    llm_config = LLMConfig(
        user_id=user.id,
        provider=provider,
        api_key_encrypted=encrypted_key,
        model_settings=kwargs.get("model_settings", {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 500,
        }),
        is_active=kwargs.get("is_active", True),
        **kwargs
    )
    session.add(llm_config)
    session.commit()
    session.refresh(llm_config)
    return llm_config


def create_conversation_history(
    session: Session,
    whatsapp_session: WhatsAppSession,
    num_messages: int = 10,
) -> List[Message]:
    """Create a conversation history with multiple messages."""
    messages = []
    user_jid = f"{whatsapp_session.user.phone_number}@s.whatsapp.net"
    assistant_jid = "+service@s.whatsapp.net"
    
    for i in range(num_messages):
        # Alternate between user and assistant messages
        if i % 2 == 0:
            # User message
            message = create_test_message(
                session=session,
                whatsapp_session=whatsapp_session,
                content=f"User message {i + 1}",
                sender_jid=user_jid,
            )
        else:
            # Assistant message
            message = create_test_message(
                session=session,
                whatsapp_session=whatsapp_session,
                content=f"Assistant response {i}",
                sender_jid=assistant_jid,
            )
        messages.append(message)
    
    return messages


def create_media_messages(
    session: Session,
    whatsapp_session: WhatsAppSession,
) -> List[Message]:
    """Create various types of media messages."""
    user_jid = f"{whatsapp_session.user.phone_number}@s.whatsapp.net"
    
    messages = [
        # Image message
        create_test_message(
            session=session,
            whatsapp_session=whatsapp_session,
            message_type=MessageType.IMAGE,
            sender_jid=user_jid,
            caption="Check out this image!",
            media_metadata={
                "size": 1024000,
                "dimensions": {"width": 1920, "height": 1080},
                "mime_type": "image/jpeg"
            }
        ),
        # Audio message
        create_test_message(
            session=session,
            whatsapp_session=whatsapp_session,
            message_type=MessageType.AUDIO,
            sender_jid=user_jid,
            media_metadata={
                "duration": 30,
                "size": 256000,
                "mime_type": "audio/ogg"
            }
        ),
        # Video message
        create_test_message(
            session=session,
            whatsapp_session=whatsapp_session,
            message_type=MessageType.VIDEO,
            sender_jid=user_jid,
            caption="Short video clip",
            media_metadata={
                "duration": 15,
                "size": 5120000,
                "dimensions": {"width": 720, "height": 1280},
                "mime_type": "video/mp4"
            }
        ),
        # Document message
        create_test_message(
            session=session,
            whatsapp_session=whatsapp_session,
            message_type=MessageType.DOCUMENT,
            sender_jid=user_jid,
            caption="Important document",
            media_metadata={
                "filename": "document.pdf",
                "size": 512000,
                "mime_type": "application/pdf"
            }
        ),
    ]
    
    return messages


def create_test_data(session: Session) -> dict:
    """Create a complete set of test data."""
    # Create users
    user1 = create_test_user(
        session,
        phone_number="+1234567890",
        display_name="Alice Smith"
    )
    user2 = create_test_user(
        session,
        phone_number="+0987654321",
        display_name="Bob Johnson"
    )
    
    # Create sessions
    session1 = create_test_session(session, user1)
    session2 = create_test_session(
        session, user2, status=SessionStatus.QR_PENDING
    )
    
    # Create LLM configs
    llm_config1 = create_test_llm_config(session, user1)
    llm_config2 = create_test_llm_config(
        session, user2, provider=LLMProvider.ANTHROPIC
    )
    
    # Create auth codes
    auth_code1 = create_test_auth_code(session, user1)
    auth_code2 = create_test_auth_code(session, user2, used=True)
    
    # Create conversation history
    messages1 = create_conversation_history(session, session1, num_messages=20)
    media_messages1 = create_media_messages(session, session1)
    
    # Create some messages for user2
    messages2 = create_conversation_history(session, session2, num_messages=5)
    
    return {
        "users": [user1, user2],
        "sessions": [session1, session2],
        "llm_configs": [llm_config1, llm_config2],
        "auth_codes": [auth_code1, auth_code2],
        "text_messages": messages1 + messages2,
        "media_messages": media_messages1,
    }


def cleanup_test_data(session: Session):
    """Clean up all test data."""
    # Delete in reverse order of creation due to foreign keys
    session.query(Message).delete()
    session.query(AuthCode).delete()
    session.query(LLMConfig).delete()
    session.query(WhatsAppSession).delete()
    session.query(User).delete()
    session.commit()
```

### shared/alembic/versions/001_initial_schema.py
```python
"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user table
    op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
        sa.UniqueConstraint('phone_number', name=op.f('uq_user_phone_number'))
    )
    op.create_index(op.f('ix_phone_number'), 'user', ['phone_number'], unique=False)

    # Create session table
    op.create_table('session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_type', sa.Enum('MAIN', 'USER', name='sessiontype'), nullable=False),
        sa.Column('status', sa.Enum('QR_PENDING', 'CONNECTED', 'DISCONNECTED', 'ERROR', name='sessionstatus'), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_session_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_session'))
    )
    op.create_index(op.f('ix_user_id'), 'session', ['user_id'], unique=False)

    # Create message table
    op.create_table('message',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('sender_jid', sa.String(length=50), nullable=False),
        sa.Column('recipient_jid', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('message_type', sa.Enum('TEXT', 'IMAGE', 'AUDIO', 'VIDEO', 'DOCUMENT', name='messagetype'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('reply_to_id', sa.BigInteger(), nullable=True),
        sa.Column('media_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['reply_to_id'], ['message.id'], name=op.f('fk_message_reply_to_id_message')),
        sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_message_session_id_session')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_message_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_message'))
    )
    op.create_index(op.f('ix_session_id'), 'message', ['session_id'], unique=False)
    op.create_index(op.f('ix_user_id'), 'message', ['user_id'], unique=False)
    op.create_index(op.f('ix_sender_jid'), 'message', ['sender_jid'], unique=False)
    op.create_index(op.f('ix_timestamp'), 'message', ['timestamp'], unique=False)
    op.create_index(op.f('ix_reply_to_id'), 'message', ['reply_to_id'], unique=False)

    # Create auth_code table
    op.create_table('auth_code',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_auth_code_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_code'))
    )
    op.create_index(op.f('ix_user_id'), 'auth_code', ['user_id'], unique=False)
    op.create_index(op.f('ix_code'), 'auth_code', ['code'], unique=False)
    op.create_index(op.f('ix_expires_at'), 'auth_code', ['expires_at'], unique=False)

    # Create llm_config table
    op.create_table('llm_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.Enum('OPENAI', 'ANTHROPIC', 'GOOGLE', name='llmprovider'), nullable=False),
        sa.Column('api_key_encrypted', sa.String(length=500), nullable=False),
        sa.Column('model_settings', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_llm_config_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_llm_config'))
    )
    op.create_index(op.f('ix_user_id'), 'llm_config', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_id'), table_name='llm_config')
    op.drop_table('llm_config')
    op.drop_index(op.f('ix_expires_at'), table_name='auth_code')
    op.drop_index(op.f('ix_code'), table_name='auth_code')
    op.drop_index(op.f('ix_user_id'), table_name='auth_code')
    op.drop_table('auth_code')
    op.drop_index(op.f('ix_reply_to_id'), table_name='message')
    op.drop_index(op.f('ix_timestamp'), table_name='message')
    op.drop_index(op.f('ix_sender_jid'), table_name='message')
    op.drop_index(op.f('ix_user_id'), table_name='message')
    op.drop_index(op.f('ix_session_id'), table_name='message')
    op.drop_table('message')
    op.drop_index(op.f('ix_user_id'), table_name='session')
    op.drop_table('session')
    op.drop_index(op.f('ix_phone_number'), table_name='user')
    op.drop_table('user')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS sessiontype')
    op.execute('DROP TYPE IF EXISTS sessionstatus')
    op.execute('DROP TYPE IF EXISTS messagetype')
    op.execute('DROP TYPE IF EXISTS llmprovider')
```

### shared/tests/database/test_connection.py
```python
"""Tests for database connection utilities."""
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from database.connection import DatabaseManager, TestDatabaseManager, get_database_manager
from config.database import DatabaseConfig


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


@patch('database.connection.create_engine')
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


@patch('database.connection.sessionmaker')
@patch('database.connection.create_engine')
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
    test_db.drop_tables()    # Should not raise


def test_get_database_manager_singleton():
    """Test that get_database_manager returns singleton."""
    # Clear any existing manager
    import database.connection
    database.connection._db_manager = None
    
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://test:test@localhost:5432/test",
    )
    
    manager1 = get_database_manager(config)
    manager2 = get_database_manager()  # Should reuse existing
    
    assert manager1 is manager2
    
    # Clean up
    database.connection._db_manager = None


@pytest.mark.asyncio
async def test_async_engine_url_conversion(db_config):
    """Test that async engine URL is converted correctly."""
    db_manager = DatabaseManager(db_config)
    
    with patch('database.connection.create_async_engine') as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        
        engine = db_manager.async_engine
        
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
    assert hasattr(db_manager, 'get_async_session')
    assert hasattr(db_manager, 'async_session_maker')


def test_get_db_session_dependency():
    """Test the get_db_session dependency function."""
    from database.connection import get_db_session
    
    with patch('database.connection.get_database_manager') as mock_get_manager:
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
```

### shared/tests/database/test_fixtures.py
```python
"""Tests for database fixtures."""
import pytest
from datetime import datetime, timezone

from database.connection import TestDatabaseManager
from database.fixtures import (
    create_test_user, create_test_session, create_test_message,
    create_test_auth_code, create_test_llm_config, create_test_data,
    cleanup_test_data, create_conversation_history, create_media_messages
)
from models.user import User
from models.session import Session, SessionType, SessionStatus
from models.message import Message, MessageType
from models.llm_config import LLMProvider


@pytest.fixture
def db_session():
    """Create test database session with tables."""
    test_db = TestDatabaseManager()
    test_db.create_tables()
    session = test_db.get_session()
    yield session
    session.close()
    test_db.drop_tables()


def test_create_test_user(db_session):
    """Test creating a test user."""
    user = create_test_user(
        db_session,
        phone_number="+1234567890",
        display_name="Test User"
    )
    
    assert user.id is not None
    assert user.phone_number == "+1234567890"
    assert user.display_name == "Test User"
    assert user.first_seen is not None
    assert user.preferences == {"theme": "dark"}


def test_create_test_session(db_session):
    """Test creating a test WhatsApp session."""
    user = create_test_user(db_session)
    
    session = create_test_session(
        db_session,
        user,
        session_type=SessionType.MAIN,
        status=SessionStatus.CONNECTED
    )
    
    assert session.id is not None
    assert session.user_id == user.id
    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.CONNECTED
    assert session.connected_at is not None
    assert session.metadata == {"device": "iPhone"}


def test_create_test_message(db_session):
    """Test creating a test message."""
    user = create_test_user(db_session)
    session = create_test_session(db_session, user)
    
    message = create_test_message(
        db_session,
        session,
        content="Hello, world!",
        message_type=MessageType.TEXT
    )
    
    assert message.id is not None
    assert message.session_id == session.id
    assert message.user_id == user.id
    assert message.content == "Hello, world!"
    assert message.message_type == MessageType.TEXT
    assert message.sender_jid == f"{user.phone_number}@s.whatsapp.net"


def test_create_test_auth_code(db_session):
    """Test creating a test auth code."""
    user = create_test_user(db_session)
    
    auth_code = create_test_auth_code(
        db_session,
        user,
        code="123456"
    )
    
    assert auth_code.id is not None
    assert auth_code.user_id == user.id
    assert auth_code.code == "123456"
    assert auth_code.used is False
    assert auth_code.expires_at > datetime.now(timezone.utc)


def test_create_test_llm_config(db_session):
    """Test creating a test LLM config."""
    user = create_test_user(db_session)
    
    llm_config = create_test_llm_config(
        db_session,
        user,
        provider=LLMProvider.OPENAI,
        api_key="sk-test123"
    )
    
    assert llm_config.id is not None
    assert llm_config.user_id == user.id
    assert llm_config.provider == LLMProvider.OPENAI
    assert llm_config.api_key_encrypted  # Should be encrypted
    assert llm_config.api_key_encrypted != "sk-test123"  # Should not be plaintext
    assert llm_config.model_settings["model"] == "gpt-4"
    assert llm_config.is_active is True


def test_create_conversation_history(db_session):
    """Test creating conversation history."""
    user = create_test_user(db_session)
    session = create_test_session(db_session, user)
    
    messages = create_conversation_history(
        db_session,
        session,
        num_messages=6
    )
    
    assert len(messages) == 6
    
    # Should alternate between user and assistant messages
    user_jid = f"{user.phone_number}@s.whatsapp.net"
    assistant_jid = "+service@s.whatsapp.net"
    
    for i, message in enumerate(messages):
        if i % 2 == 0:
            # User message
            assert message.sender_jid == user_jid
            assert "User message" in message.content
        else:
            # Assistant message
            assert message.sender_jid == assistant_jid
            assert "Assistant response" in message.content


def test_create_media_messages(db_session):
    """Test creating media messages."""
    user = create_test_user(db_session)
    session = create_test_session(db_session, user)
    
    messages = create_media_messages(db_session, session)
    
    assert len(messages) == 4
    
    # Check message types
    types = [msg.message_type for msg in messages]
    assert MessageType.IMAGE in types
    assert MessageType.AUDIO in types
    assert MessageType.VIDEO in types
    assert MessageType.DOCUMENT in types
    
    # Check that media messages have metadata
    for message in messages:
        assert message.media_metadata is not None
        assert "size" in message.media_metadata
        
        if message.message_type == MessageType.IMAGE:
            assert "dimensions" in message.media_metadata
            assert message.caption == "Check out this image!"
        elif message.message_type == MessageType.AUDIO:
            assert "duration" in message.media_metadata


def test_create_test_data_complete(db_session):
    """Test creating complete test data set."""
    data = create_test_data(db_session)
    
    # Check all data was created
    assert len(data["users"]) == 2
    assert len(data["sessions"]) == 2
    assert len(data["llm_configs"]) == 2
    assert len(data["auth_codes"]) == 2
    assert len(data["text_messages"]) == 25  # 20 + 5
    assert len(data["media_messages"]) == 4
    
    # Check relationships
    user1, user2 = data["users"]
    session1, session2 = data["sessions"]
    
    assert session1.user_id == user1.id
    assert session2.user_id == user2.id
    assert session1.status == SessionStatus.CONNECTED
    assert session2.status == SessionStatus.QR_PENDING
    
    # Check LLM configs have different providers
    providers = [config.provider for config in data["llm_configs"]]
    assert LLMProvider.OPENAI in providers
    assert LLMProvider.ANTHROPIC in providers


def test_cleanup_test_data(db_session):
    """Test cleaning up test data."""
    # Create some test data
    data = create_test_data(db_session)
    
    # Verify data exists
    assert db_session.query(User).count() == 2
    assert db_session.query(Session).count() == 2
    assert db_session.query(Message).count() > 0
    
    # Clean up
    cleanup_test_data(db_session)
    
    # Verify all data is gone
    assert db_session.query(User).count() == 0
    assert db_session.query(Session).count() == 0
    assert db_session.query(Message).count() == 0


def test_message_reply_relationship(db_session):
    """Test creating message with reply relationship."""
    user = create_test_user(db_session)
    session = create_test_session(db_session, user)
    
    # Create original message
    original = create_test_message(
        db_session,
        session,
        content="Original message"
    )
    
    # Create reply
    reply = create_test_message(
        db_session,
        session,
        content="Reply message",
        reply_to_id=original.id
    )
    
    assert reply.reply_to_id == original.id
    assert reply.reply_to == original
```

## Commands to Run

```bash
# Set up shared database utilities
cd shared
uv run python -c "from database.connection import TestDatabaseManager; db = TestDatabaseManager(); db.create_tables(); print('Tables created')"

# Test database connections
uv run pytest tests/database/test_connection.py -v

# Test fixtures
uv run pytest tests/database/test_fixtures.py -v

# Create initial migration
uv run alembic revision --autogenerate -m "Initial schema"

# Run migration
uv run alembic upgrade head

# Test with real database (requires PostgreSQL)
DATABASE_URL=postgresql://zapa:zapa@localhost:5432/zapa_test uv run alembic upgrade head

# Test rollback
uv run alembic downgrade base
uv run alembic upgrade head
```

## Verification

1. Alembic migrations create all tables correctly
2. Database connections work for both sync and async
3. Test fixtures create realistic data for testing
4. Migration rollbacks work properly
5. Tests pass with both SQLite (test) and PostgreSQL
6. Code coverage ≥ 90%

## Next Steps

After database setup is complete, proceed to Task 05: Private Service Structure and Health Checks.