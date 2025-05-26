from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.auth import AuthCodeRequest, AuthCodeVerify, AuthToken
from schemas.llm import LLMConfigCreate, LLMConfigResponse, LLMConfigUpdate, LLMProvider
from schemas.message import MessageCreate, MessageResponse, MessageType
from schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionStatus,
    SessionType,
    SessionUpdate,
)
from schemas.user import UserCreate, UserResponse, UserUpdate


def test_user_create_schema():
    """Test UserCreate schema validation."""
    # Valid user
    user = UserCreate(
        phone_number="+1234567890",
        display_name="Test User",
        preferences={"theme": "dark"},
    )
    assert user.phone_number == "+1234567890"
    assert user.display_name == "Test User"

    # Phone number too short
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(phone_number="123")
    assert "at least 10 characters" in str(exc_info.value)


def test_user_update_schema():
    """Test UserUpdate schema with optional fields."""
    # All fields None is valid
    update = UserUpdate()
    assert update.display_name is None
    assert update.preferences is None

    # Partial update
    update = UserUpdate(display_name="New Name")
    assert update.display_name == "New Name"
    assert update.preferences is None


def test_user_response_schema():
    """Test UserResponse from ORM model."""
    # Simulate data from database
    user_data = {
        "id": 1,
        "phone_number": "+1234567890",
        "display_name": "Test User",
        "preferences": {"theme": "dark"},
        "first_seen": datetime.now(timezone.utc),
        "last_active": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    response = UserResponse(**user_data)
    assert response.id == 1
    assert response.phone_number == "+1234567890"
    assert response.last_active is None


def test_session_create_schema():
    """Test SessionCreate schema."""
    session = SessionCreate(
        user_id=1,
        session_type=SessionType.MAIN,
        status=SessionStatus.CONNECTED,
        session_metadata={"device": "iPhone"},
    )
    assert session.user_id == 1
    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.CONNECTED


def test_session_update_schema():
    """Test SessionUpdate schema."""
    update = SessionUpdate(status=SessionStatus.DISCONNECTED)
    assert update.status == SessionStatus.DISCONNECTED
    assert update.connected_at is None


def test_session_response_schema():
    """Test SessionResponse schema."""
    session_data = {
        "id": 1,
        "user_id": 1,
        "session_type": SessionType.MAIN,
        "status": SessionStatus.CONNECTED,
        "connected_at": datetime.now(timezone.utc),
        "disconnected_at": None,
        "session_metadata": {"device": "iPhone"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    response = SessionResponse(**session_data)
    assert response.id == 1
    assert response.session_type == SessionType.MAIN


def test_message_create_schema():
    """Test MessageCreate schema validation."""
    msg = MessageCreate(
        session_id=1,
        user_id=1,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Hello, world!",
    )
    assert msg.message_type == MessageType.TEXT
    assert msg.content == "Hello, world!"

    # Media message without content
    media_msg = MessageCreate(
        session_id=1,
        user_id=1,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.IMAGE,
        caption="Nice photo!",
        media_metadata={"size": 1024000, "dimensions": {"width": 1920, "height": 1080}},
    )
    assert media_msg.content is None
    assert media_msg.caption == "Nice photo!"


def test_message_response_schema():
    """Test MessageResponse schema."""
    message_data = {
        "id": 1,
        "session_id": 1,
        "user_id": 1,
        "sender_jid": "+1234567890@s.whatsapp.net",
        "recipient_jid": "+0987654321@s.whatsapp.net",
        "timestamp": datetime.now(timezone.utc),
        "message_type": MessageType.TEXT,
        "content": "Hello",
        "caption": None,
        "reply_to_id": None,
        "media_metadata": None,
        "created_at": datetime.now(timezone.utc),
    }

    response = MessageResponse(**message_data)
    assert response.id == 1
    assert response.content == "Hello"


def test_auth_code_request_schema():
    """Test AuthCodeRequest schema."""
    request = AuthCodeRequest(phone_number="+1234567890")
    assert request.phone_number == "+1234567890"

    # Invalid phone number format (too short)
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="invalid")

    # Invalid phone number format (pattern)
    with pytest.raises(ValidationError) as exc_info:
        AuthCodeRequest(phone_number="invalidnumber123")
    assert "Invalid phone number format" in str(exc_info.value)

    # Phone number without +
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="1234567890")

    # Phone number starting with 0
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="+0234567890")


def test_auth_code_verify_schema():
    """Test AuthCodeVerify schema."""
    verify = AuthCodeVerify(phone_number="+1234567890", code="123456")
    assert verify.code == "123456"

    # Code too short
    with pytest.raises(ValidationError):
        AuthCodeVerify(phone_number="+1234567890", code="12345")  # Too short

    # Code must be 6 digits
    with pytest.raises(ValidationError) as exc_info:
        AuthCodeVerify(phone_number="+1234567890", code="12345a")
    assert "Code must be 6 digits" in str(exc_info.value)

    # Code too long
    with pytest.raises(ValidationError):
        AuthCodeVerify(phone_number="+1234567890", code="1234567")


def test_auth_token_schema():
    """Test AuthToken schema."""
    token = AuthToken(access_token="jwt_token_here", user_id=1)
    assert token.access_token == "jwt_token_here"
    assert token.token_type == "bearer"
    assert token.expires_in == 3600
    assert token.user_id == 1


def test_llm_config_create_schema():
    """Test LLMConfigCreate schema."""
    config = LLMConfigCreate(
        provider=LLMProvider.OPENAI,
        api_key="sk-test123",
        model_settings={"model": "gpt-4", "temperature": 0.7},
    )
    assert config.provider == LLMProvider.OPENAI
    assert config.api_key == "sk-test123"

    # Invalid provider
    with pytest.raises(ValidationError):
        LLMConfigCreate(provider="invalid_provider", api_key="test")

    # Empty api_key
    with pytest.raises(ValidationError):
        LLMConfigCreate(provider=LLMProvider.OPENAI, api_key="")


def test_llm_config_update_schema():
    """Test LLMConfigUpdate schema."""
    update = LLMConfigUpdate(is_active=False)
    assert update.is_active is False
    assert update.api_key is None

    # All None is valid
    update = LLMConfigUpdate()
    assert update.api_key is None
    assert update.model_settings is None
    assert update.is_active is None


def test_llm_config_response_schema():
    """Test LLMConfigResponse schema."""
    config_data = {
        "id": 1,
        "user_id": 1,
        "provider": LLMProvider.ANTHROPIC,
        "model_settings": {"model": "claude-3", "temperature": 0.5},
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    response = LLMConfigResponse(**config_data)
    assert response.id == 1
    assert response.provider == LLMProvider.ANTHROPIC
    assert response.model_settings["model"] == "claude-3"


def test_message_type_enum():
    """Test MessageType enum values."""
    assert MessageType.TEXT.value == "text"
    assert MessageType.IMAGE.value == "image"
    assert MessageType.AUDIO.value == "audio"
    assert MessageType.VIDEO.value == "video"
    assert MessageType.DOCUMENT.value == "document"

    # All valid types
    for msg_type in ["text", "image", "audio", "video", "document"]:
        assert MessageType(msg_type)

    # Invalid type
    with pytest.raises(ValueError):
        MessageType("invalid")


def test_session_type_enum():
    """Test SessionType enum values."""
    assert SessionType.MAIN.value == "main"
    assert SessionType.USER.value == "user"


def test_session_status_enum():
    """Test SessionStatus enum values."""
    assert SessionStatus.QR_PENDING.value == "qr_pending"
    assert SessionStatus.CONNECTED.value == "connected"
    assert SessionStatus.DISCONNECTED.value == "disconnected"
    assert SessionStatus.ERROR.value == "error"


def test_llm_provider_enum():
    """Test LLMProvider enum values."""
    assert LLMProvider.OPENAI.value == "openai"
    assert LLMProvider.ANTHROPIC.value == "anthropic"
    assert LLMProvider.GOOGLE.value == "google"


def test_user_create_minimal():
    """Test UserCreate with minimal required fields."""
    user = UserCreate(phone_number="+1234567890")
    assert user.phone_number == "+1234567890"
    assert user.display_name is None
    assert user.preferences == {}


def test_user_create_default_preferences():
    """Test UserCreate with default preferences."""
    user = UserCreate(phone_number="+1234567890", display_name="Test")
    assert user.preferences == {}

    # Custom preferences
    user2 = UserCreate(
        phone_number="+1234567890", preferences={"theme": "dark", "lang": "en"}
    )
    assert user2.preferences["theme"] == "dark"
    assert user2.preferences["lang"] == "en"


def test_session_create_defaults():
    """Test SessionCreate with default values."""
    session = SessionCreate(user_id=1)
    assert session.user_id == 1
    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.DISCONNECTED
    assert session.session_metadata == {}


def test_auth_code_request_edge_cases():
    """Test AuthCodeRequest with edge cases."""
    # Shortest valid number
    request = AuthCodeRequest(phone_number="+1234567890")
    assert request.phone_number == "+1234567890"

    # Longest valid number (15 digits total)
    request = AuthCodeRequest(phone_number="+123456789012345")
    assert request.phone_number == "+123456789012345"

    # Too long
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="+1234567890123456")  # 16 digits


def test_message_create_reply():
    """Test MessageCreate with reply."""
    msg = MessageCreate(
        session_id=1,
        user_id=1,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="This is a reply",
        reply_to_id=42,
    )
    assert msg.reply_to_id == 42
    assert msg.content == "This is a reply"
