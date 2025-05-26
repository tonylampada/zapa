"""Tests for database fixtures."""
from datetime import datetime, timezone

import pytest

from app.database.connection import TestDatabaseManager
from app.database.fixtures import (
    cleanup_test_data,
    create_conversation_history,
    create_media_messages,
    create_test_auth_code,
    create_test_data,
    create_test_llm_config,
    create_test_message,
    create_test_session,
    create_test_user,
)
from models.llm_config import LLMProvider
from models.message import Message, MessageType
from models.session import Session, SessionStatus, SessionType
from models.user import User


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
        db_session, phone_number="+1234567890", display_name="Test User"
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
        db_session, user, session_type=SessionType.MAIN, status=SessionStatus.CONNECTED
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
        db_session, session, content="Hello, world!", message_type=MessageType.TEXT
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

    auth_code = create_test_auth_code(db_session, user, code="123456")

    assert auth_code.id is not None
    assert auth_code.user_id == user.id
    assert auth_code.code == "123456"
    assert auth_code.used is False
    # Compare with timezone-aware datetime
    now = datetime.now(timezone.utc)
    assert auth_code.expires_at.replace(tzinfo=timezone.utc) > now


def test_create_test_llm_config(db_session):
    """Test creating a test LLM config."""
    user = create_test_user(db_session)

    llm_config = create_test_llm_config(
        db_session, user, provider=LLMProvider.OPENAI, api_key="sk-test123"
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

    messages = create_conversation_history(db_session, session, num_messages=6)

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
    _ = create_test_data(db_session)

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
    original = create_test_message(db_session, session, content="Original message")

    # Create reply
    reply = create_test_message(
        db_session, session, content="Reply message", reply_to_id=original.id
    )

    assert reply.reply_to_id == original.id
    assert reply.reply_to == original
