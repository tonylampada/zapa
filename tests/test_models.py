from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.auth_code import AuthCode
from models.base import Base
from models.llm_config import LLMConfig, LLMProvider
from models.message import Message, MessageType
from models.session import Session, SessionStatus, SessionType
from models.user import User


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    session = session_local()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


def test_user_model(db_session):
    """Test User model creation and properties."""
    user = User(
        phone_number="+1234567890",
        display_name="Test User",
        first_seen=datetime.now(timezone.utc),
        preferences={"theme": "dark"},
    )
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.phone_number == "+1234567890"
    assert user.display_name == "Test User"
    assert user.preferences["theme"] == "dark"
    assert user.created_at is not None


def test_user_unique_phone_number(db_session):
    """Test phone number uniqueness constraint."""
    user1 = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    user2 = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))

    db_session.add(user1)
    db_session.commit()

    db_session.add(user2)
    with pytest.raises(Exception):  # SQLAlchemy IntegrityError
        db_session.commit()


def test_session_model(db_session):
    """Test Session model with user relationship."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    session = Session(
        user_id=user.id,
        session_type=SessionType.MAIN,
        status=SessionStatus.CONNECTED,
        connected_at=datetime.now(timezone.utc),
        session_metadata={"device": "iPhone"},
    )
    db_session.add(session)
    db_session.commit()

    assert session.id is not None
    assert session.user_id == user.id
    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.CONNECTED
    assert session.session_metadata["device"] == "iPhone"

    # Test relationship
    assert session.user == user
    assert user.sessions[0] == session


def test_message_model(db_session):
    """Test Message model with all fields."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    session = Session(
        user_id=user.id, session_type=SessionType.MAIN, status=SessionStatus.CONNECTED
    )
    db_session.add(session)
    db_session.commit()

    # Text message
    text_msg = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Hello, world!",
    )
    db_session.add(text_msg)
    db_session.commit()

    assert text_msg.id is not None
    assert text_msg.content == "Hello, world!"
    assert text_msg.message_type == MessageType.TEXT

    # Media message with metadata
    media_msg = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.IMAGE,
        caption="Check this out!",
        media_metadata={
            "size": 1024000,
            "dimensions": {"width": 1920, "height": 1080},
            "mime_type": "image/jpeg",
        },
    )
    db_session.add(media_msg)
    db_session.commit()

    assert media_msg.content is None  # No content for media
    assert media_msg.caption == "Check this out!"
    assert media_msg.media_metadata["dimensions"]["width"] == 1920


def test_message_reply(db_session):
    """Test message reply relationship."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    session = Session(user_id=user.id)
    db_session.add(session)
    db_session.commit()

    original = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Original message",
    )
    db_session.add(original)
    db_session.commit()

    reply = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+0987654321@s.whatsapp.net",
        recipient_jid="+1234567890@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Reply message",
        reply_to_id=original.id,
    )
    db_session.add(reply)
    db_session.commit()

    assert reply.reply_to == original
    assert reply.reply_to_id == original.id


def test_auth_code_model(db_session):
    """Test AuthCode model."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    auth_code = AuthCode(
        user_id=user.id,
        code="123456",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(auth_code)
    db_session.commit()

    assert auth_code.id is not None
    assert auth_code.code == "123456"
    assert auth_code.used is False
    assert auth_code.user == user


def test_llm_config_model(db_session):
    """Test LLMConfig model."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    llm_config = LLMConfig(
        user_id=user.id,
        provider=LLMProvider.OPENAI,
        api_key_encrypted="encrypted_key_here",
        model_settings={"model": "gpt-4", "temperature": 0.7, "max_tokens": 500},
    )
    db_session.add(llm_config)
    db_session.commit()

    assert llm_config.id is not None
    assert llm_config.provider == LLMProvider.OPENAI
    assert llm_config.is_active is True
    assert llm_config.model_settings["model"] == "gpt-4"
    assert llm_config.user == user


def test_cascade_deletion(db_session):
    """Test cascade deletion of related records."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    session = Session(user_id=user.id)
    db_session.add(session)
    db_session.commit()

    message = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Test",
    )
    db_session.add(message)
    db_session.commit()

    # Delete user should cascade to session and message
    db_session.delete(user)
    db_session.commit()

    assert db_session.query(User).count() == 0
    assert db_session.query(Session).count() == 0
    assert db_session.query(Message).count() == 0


def test_session_enums():
    """Test session enum values."""
    assert SessionType.MAIN.value == "main"
    assert SessionType.USER.value == "user"

    assert SessionStatus.QR_PENDING.value == "qr_pending"
    assert SessionStatus.CONNECTED.value == "connected"
    assert SessionStatus.DISCONNECTED.value == "disconnected"
    assert SessionStatus.ERROR.value == "error"


def test_message_type_enum():
    """Test MessageType enum values."""
    assert MessageType.TEXT.value == "text"
    assert MessageType.IMAGE.value == "image"
    assert MessageType.AUDIO.value == "audio"
    assert MessageType.VIDEO.value == "video"
    assert MessageType.DOCUMENT.value == "document"


def test_llm_provider_enum():
    """Test LLMProvider enum values."""
    assert LLMProvider.OPENAI.value == "openai"
    assert LLMProvider.ANTHROPIC.value == "anthropic"
    assert LLMProvider.GOOGLE.value == "google"


def test_user_minimal_required_fields(db_session):
    """Test user creation with minimal required fields."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.display_name is None
    assert user.last_active is None
    assert user.preferences == {}


def test_session_default_values(db_session):
    """Test session default values."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    session = Session(user_id=user.id)
    db_session.add(session)
    db_session.commit()

    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.DISCONNECTED
    assert session.connected_at is None
    assert session.disconnected_at is None
    assert session.session_metadata == {}


def test_auth_code_default_values(db_session):
    """Test AuthCode default values."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    auth_code = AuthCode(
        user_id=user.id,
        code="123456",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(auth_code)
    db_session.commit()

    assert auth_code.used is False


def test_llm_config_default_values(db_session):
    """Test LLMConfig default values."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    llm_config = LLMConfig(
        user_id=user.id,
        provider=LLMProvider.ANTHROPIC,
        api_key_encrypted="encrypted_key",
    )
    db_session.add(llm_config)
    db_session.commit()

    assert llm_config.is_active is True
    assert llm_config.model_settings == {}


def test_base_model_timestamps(db_session):
    """Test that base model adds timestamps correctly."""
    user = User(phone_number="+1234567890", first_seen=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    # Check created_at is set
    assert user.created_at is not None
    assert isinstance(user.created_at, datetime)

    # Check updated_at is None initially
    assert user.updated_at is None

    # Update the user
    user.display_name = "Updated Name"
    db_session.commit()

    # updated_at should still be None in SQLite (no trigger)
    # In PostgreSQL with proper setup, this would be set
