"""Test fixtures and sample data creation."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config.encryption import EncryptionManager
from models.auth_code import AuthCode
from models.llm_config import LLMConfig, LLMProvider
from models.message import Message, MessageType
from models.session import Session as WhatsAppSession
from models.session import SessionStatus, SessionType
from models.user import User


def create_test_user(
    session: Session, phone_number: str = "+1234567890", display_name: str = "Test User", **kwargs
) -> User:
    """Create a test user."""
    user = User(
        phone_number=phone_number,
        display_name=display_name,
        first_seen=datetime.now(timezone.utc),
        preferences=kwargs.get("preferences", {"theme": "dark"}),
        **kwargs,
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
    **kwargs,
) -> WhatsAppSession:
    """Create a test WhatsApp session."""
    whatsapp_session = WhatsAppSession(
        user_id=user.id,
        session_type=session_type,
        status=status,
        connected_at=datetime.now(timezone.utc) if status == SessionStatus.CONNECTED else None,
        metadata=kwargs.get("metadata", {"device": "iPhone"}),
        **kwargs,
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
    sender_jid: str | None = None,
    **kwargs,
) -> Message:
    """Create a test message."""
    if sender_jid is None:
        sender_jid = f"{whatsapp_session.user.phone_number}@s.whatsapp.net"

    # Extract known kwargs to avoid conflicts
    caption = kwargs.pop("caption", None)
    reply_to_id = kwargs.pop("reply_to_id", None)
    media_metadata = kwargs.pop("media_metadata", None)

    message = Message(
        session_id=whatsapp_session.id,
        user_id=whatsapp_session.user_id,
        sender_jid=sender_jid,
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=message_type,
        content=content if message_type == MessageType.TEXT else None,
        caption=caption,
        reply_to_id=reply_to_id,
        media_metadata=media_metadata,
        **kwargs,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def create_test_auth_code(
    session: Session, user: User, code: str = "123456", expires_in_minutes: int = 5, **kwargs
) -> AuthCode:
    """Create a test auth code."""
    # Extract known kwargs to avoid conflicts
    used = kwargs.pop("used", False)

    auth_code = AuthCode(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        used=used,
        **kwargs,
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
    encryption_manager: EncryptionManager | None = None,
    **kwargs,
) -> LLMConfig:
    """Create a test LLM config."""
    if encryption_manager is None:
        encryption_manager = EncryptionManager("test_key_" + "x" * 24)

    encrypted_key = encryption_manager.encrypt(api_key)

    llm_config = LLMConfig(
        user_id=user.id,
        provider=provider,
        api_key_encrypted=encrypted_key,
        model_settings=kwargs.get(
            "model_settings",
            {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500,
            },
        ),
        is_active=kwargs.get("is_active", True),
        **kwargs,
    )
    session.add(llm_config)
    session.commit()
    session.refresh(llm_config)
    return llm_config


def create_conversation_history(
    session: Session,
    whatsapp_session: WhatsAppSession,
    num_messages: int = 10,
) -> list[Message]:
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
) -> list[Message]:
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
                "mime_type": "image/jpeg",
            },
        ),
        # Audio message
        create_test_message(
            session=session,
            whatsapp_session=whatsapp_session,
            message_type=MessageType.AUDIO,
            sender_jid=user_jid,
            media_metadata={"duration": 30, "size": 256000, "mime_type": "audio/ogg"},
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
                "mime_type": "video/mp4",
            },
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
                "mime_type": "application/pdf",
            },
        ),
    ]

    return messages


def create_test_data(session: Session) -> dict:
    """Create a complete set of test data."""
    # Create users
    user1 = create_test_user(session, phone_number="+1234567890", display_name="Alice Smith")
    user2 = create_test_user(session, phone_number="+0987654321", display_name="Bob Johnson")

    # Create sessions
    session1 = create_test_session(session, user1)
    session2 = create_test_session(session, user2, status=SessionStatus.QR_PENDING)

    # Create LLM configs
    llm_config1 = create_test_llm_config(session, user1)
    llm_config2 = create_test_llm_config(session, user2, provider=LLMProvider.ANTHROPIC)

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
