# Task 02: Database Models and Schemas

## Objective
Create SQLAlchemy models and Pydantic schemas for all entities in the system, with comprehensive tests. Models are shared between both services.

## Prerequisites
- Task 01 completed (project setup)
- Both services running with health checks
- All tests passing in CI/CD

## Success Criteria
- [ ] All database models created with proper relationships
- [ ] Pydantic schemas for validation and serialization
- [ ] Unit tests for all models and schemas
- [ ] Alembic configured for migrations
- [ ] Tests passing locally and in CI/CD
- [ ] Code coverage ≥ 90% for models/schemas

## Files to Create

### shared/pyproject.toml
```toml
[project]
name = "zapa-shared"
version = "0.1.0"
description = "Shared models and schemas for Zapa services"
requires-python = ">=3.10"
dependencies = [
    "sqlalchemy==2.0.25",
    "psycopg2-binary==2.9.9",
    "alembic==1.13.1",
    "pydantic==2.5.3",
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.4",
    "pytest-asyncio==0.23.3",
    "pytest-cov==4.1.0",
    "black==23.12.1",
    "ruff==0.1.11",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_mode = "auto"

[tool.coverage.run]
source = ["models", "schemas"]
omit = ["*/tests/*"]
```

### shared/models/__init__.py
```python
from .base import Base
from .user import User
from .session import Session
from .message import Message
from .auth_code import AuthCode
from .llm_config import LLMConfig

__all__ = [
    "Base",
    "User",
    "Session",
    "Message",
    "AuthCode",
    "LLMConfig",
]
```

### shared/models/base.py
```python
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import MetaData, DateTime, func
from datetime import datetime
from typing import Optional


# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all models."""
    metadata = metadata
    
    # Common timestamp columns
    created_at: MappedColumn[datetime] = MappedColumn(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: MappedColumn[Optional[datetime]] = MappedColumn(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
```

### shared/models/user.py
```python
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import Base


class User(Base):
    """User model representing WhatsApp users."""
    
    __tablename__ = "user"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_active: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, default=dict
    )
    
    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    auth_codes: Mapped[List["AuthCode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    llm_configs: Mapped[List["LLMConfig"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
```

### shared/models/session.py
```python
from sqlalchemy import String, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, Dict, Any
from datetime import datetime
import enum

from .base import Base


class SessionType(str, enum.Enum):
    """Type of WhatsApp session."""
    MAIN = "main"  # Main service number
    USER = "user"  # User's own number (future feature)


class SessionStatus(str, enum.Enum):
    """Status of WhatsApp session."""
    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Session(Base):
    """WhatsApp session model."""
    
    __tablename__ = "session"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    session_type: Mapped[SessionType] = mapped_column(
        Enum(SessionType), nullable=False, default=SessionType.MAIN
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.DISCONNECTED
    )
    connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, default=dict
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
```

### shared/models/message.py
```python
from sqlalchemy import String, ForeignKey, DateTime, Text, JSON, Enum, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
from datetime import datetime
import enum

from .base import Base


class MessageType(str, enum.Enum):
    """Type of WhatsApp message."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class Message(Base):
    """WhatsApp message model."""
    
    __tablename__ = "message"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True  # Redundant for performance
    )
    sender_jid: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    recipient_jid: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), nullable=False
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text  # Nullable for media messages
    )
    caption: Mapped[Optional[str]] = mapped_column(Text)
    reply_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message.id"), index=True
    )
    media_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")
    reply_to: Mapped[Optional["Message"]] = relationship(
        remote_side=[id], foreign_keys=[reply_to_id]
    )
```

### shared/models/auth_code.py
```python
from sqlalchemy import String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import Base


class AuthCode(Base):
    """Authentication code for WhatsApp-based login."""
    
    __tablename__ = "auth_code"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(
        String(6), nullable=False, index=True  # 6-digit code
    )
    used: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="auth_codes")
```

### shared/models/llm_config.py
```python
from sqlalchemy import String, ForeignKey, Boolean, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Dict, Any
import enum

from .base import Base


class LLMProvider(str, enum.Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMConfig(Base):
    """LLM configuration for a user."""
    
    __tablename__ = "llm_config"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    provider: Mapped[LLMProvider] = mapped_column(
        Enum(LLMProvider), nullable=False
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        String(500), nullable=False  # Encrypted API key
    )
    model_settings: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict  # model, temperature, max_tokens, etc.
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="llm_configs")
```

### shared/schemas/__init__.py
```python
from .user import UserCreate, UserUpdate, UserResponse
from .session import SessionCreate, SessionUpdate, SessionResponse
from .message import MessageCreate, MessageResponse
from .auth import AuthCodeRequest, AuthCodeVerify, AuthToken
from .llm import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse

__all__ = [
    # User schemas
    "UserCreate",
    "UserUpdate", 
    "UserResponse",
    # Session schemas
    "SessionCreate",
    "SessionUpdate",
    "SessionResponse",
    # Message schemas
    "MessageCreate",
    "MessageResponse",
    # Auth schemas
    "AuthCodeRequest",
    "AuthCodeVerify",
    "AuthToken",
    # LLM schemas
    "LLMConfigCreate",
    "LLMConfigUpdate",
    "LLMConfigResponse",
]
```

### shared/schemas/user.py
```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema."""
    phone_number: str = Field(..., min_length=10, max_length=20)
    display_name: Optional[str] = Field(None, max_length=255)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserCreate(UserBase):
    """Schema for creating a user."""
    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    display_name: Optional[str] = Field(None, max_length=255)
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    first_seen: datetime
    last_active: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
```

### shared/schemas/message.py
```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Message type enum."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class MessageBase(BaseModel):
    """Base message schema."""
    sender_jid: str = Field(..., max_length=50)
    recipient_jid: str = Field(..., max_length=50)
    message_type: MessageType
    content: Optional[str] = None
    caption: Optional[str] = None
    reply_to_id: Optional[int] = None
    media_metadata: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    """Schema for creating a message."""
    session_id: int
    user_id: int
    timestamp: datetime


class MessageResponse(MessageBase):
    """Schema for message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    session_id: int
    user_id: int
    timestamp: datetime
    created_at: datetime
```

### shared/tests/test_models.py
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone

from models.base import Base
from models.user import User
from models.session import Session, SessionType, SessionStatus
from models.message import Message, MessageType
from models.auth_code import AuthCode
from models.llm_config import LLMConfig, LLMProvider


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


def test_user_model(db_session):
    """Test User model creation and properties."""
    user = User(
        phone_number="+1234567890",
        display_name="Test User",
        first_seen=datetime.now(timezone.utc),
        preferences={"theme": "dark"}
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
    user1 = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    user2 = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    
    db_session.add(user1)
    db_session.commit()
    
    db_session.add(user2)
    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()


def test_session_model(db_session):
    """Test Session model with user relationship."""
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()
    
    session = Session(
        user_id=user.id,
        session_type=SessionType.MAIN,
        status=SessionStatus.CONNECTED,
        connected_at=datetime.now(timezone.utc),
        metadata={"device": "iPhone"}
    )
    db_session.add(session)
    db_session.commit()
    
    assert session.id is not None
    assert session.user_id == user.id
    assert session.session_type == SessionType.MAIN
    assert session.status == SessionStatus.CONNECTED
    assert session.metadata["device"] == "iPhone"
    
    # Test relationship
    assert session.user == user
    assert user.sessions[0] == session


def test_message_model(db_session):
    """Test Message model with all fields."""
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    session = Session(
        user_id=user.id,
        session_type=SessionType.MAIN,
        status=SessionStatus.CONNECTED
    )
    db_session.add_all([user, session])
    db_session.commit()
    
    # Text message
    text_msg = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Hello, world!"
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
            "mime_type": "image/jpeg"
        }
    )
    db_session.add(media_msg)
    db_session.commit()
    
    assert media_msg.content is None  # No content for media
    assert media_msg.caption == "Check this out!"
    assert media_msg.media_metadata["dimensions"]["width"] == 1920


def test_message_reply(db_session):
    """Test message reply relationship."""
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    session = Session(user_id=user.id)
    db_session.add_all([user, session])
    db_session.commit()
    
    original = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Original message"
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
        reply_to_id=original.id
    )
    db_session.add(reply)
    db_session.commit()
    
    assert reply.reply_to == original
    assert reply.reply_to_id == original.id


def test_auth_code_model(db_session):
    """Test AuthCode model."""
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()
    
    auth_code = AuthCode(
        user_id=user.id,
        code="123456",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db_session.add(auth_code)
    db_session.commit()
    
    assert auth_code.id is not None
    assert auth_code.code == "123456"
    assert auth_code.used is False
    assert auth_code.user == user


def test_llm_config_model(db_session):
    """Test LLMConfig model."""
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()
    
    llm_config = LLMConfig(
        user_id=user.id,
        provider=LLMProvider.OPENAI,
        api_key_encrypted="encrypted_key_here",
        model_settings={
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 500
        }
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
    user = User(
        phone_number="+1234567890",
        first_seen=datetime.now(timezone.utc)
    )
    session = Session(user_id=user.id)
    message = Message(
        session_id=session.id,
        user_id=user.id,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Test"
    )
    
    db_session.add_all([user, session, message])
    db_session.commit()
    
    # Delete user should cascade to session and message
    db_session.delete(user)
    db_session.commit()
    
    assert db_session.query(User).count() == 0
    assert db_session.query(Session).count() == 0
    assert db_session.query(Message).count() == 0
```

### shared/tests/test_schemas.py
```python
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from schemas.user import UserCreate, UserUpdate, UserResponse
from schemas.message import MessageCreate, MessageResponse, MessageType
from schemas.auth import AuthCodeRequest, AuthCodeVerify, AuthToken
from schemas.llm import LLMConfigCreate, LLMConfigUpdate, LLMProvider


def test_user_create_schema():
    """Test UserCreate schema validation."""
    # Valid user
    user = UserCreate(
        phone_number="+1234567890",
        display_name="Test User",
        preferences={"theme": "dark"}
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


def test_message_create_schema():
    """Test MessageCreate schema validation."""
    msg = MessageCreate(
        session_id=1,
        user_id=1,
        sender_jid="+1234567890@s.whatsapp.net",
        recipient_jid="+0987654321@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="Hello, world!"
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
        media_metadata={
            "size": 1024000,
            "dimensions": {"width": 1920, "height": 1080}
        }
    )
    assert media_msg.content is None
    assert media_msg.caption == "Nice photo!"


def test_auth_code_request_schema():
    """Test AuthCodeRequest schema."""
    request = AuthCodeRequest(phone_number="+1234567890")
    assert request.phone_number == "+1234567890"
    
    # Invalid phone number format
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="invalid")


def test_auth_code_verify_schema():
    """Test AuthCodeVerify schema."""
    verify = AuthCodeVerify(
        phone_number="+1234567890",
        code="123456"
    )
    assert verify.code == "123456"
    
    # Code must be 6 digits
    with pytest.raises(ValidationError):
        AuthCodeVerify(
            phone_number="+1234567890",
            code="12345"  # Too short
        )


def test_llm_config_create_schema():
    """Test LLMConfigCreate schema."""
    config = LLMConfigCreate(
        provider=LLMProvider.OPENAI,
        api_key="sk-test123",
        model_settings={
            "model": "gpt-4",
            "temperature": 0.7
        }
    )
    assert config.provider == LLMProvider.OPENAI
    assert config.api_key == "sk-test123"
    
    # Invalid provider
    with pytest.raises(ValidationError):
        LLMConfigCreate(
            provider="invalid_provider",
            api_key="test"
        )


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
```

### shared/alembic.ini
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://zapa:zapa@localhost:5432/zapa

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### Update services to use shared models

### services/private/pyproject.toml (updated dependencies)
```toml
dependencies = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "httpx==0.26.0",
    "zapa-shared @ file://../../shared",  # Reference shared package
]
```

### services/public/pyproject.toml (updated dependencies)
```toml
dependencies = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "httpx==0.26.0",
    "python-jose[cryptography]==3.3.0",
    "zapa-shared @ file://../../shared",  # Reference shared package
]
```

### Update CI workflow

Add to `.github/workflows/ci.yml`:

```yaml
  test-shared:
    name: Test Shared Components
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: shared
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
    
    - name: Create virtual environment
      run: uv venv
    
    - name: Install dependencies
      run: |
        uv pip install -e ".[dev]"
    
    - name: Run linting
      run: |
        uv run black --check models schemas tests
        uv run ruff check models schemas tests
    
    - name: Run tests with coverage
      run: |
        uv run pytest -v --cov=models --cov=schemas --cov-report=term-missing --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./shared/coverage.xml
        flags: shared
        name: shared-coverage

  all-tests-pass:
    name: All Tests Pass
    needs: [test-private-service, test-public-service, test-shared]
    runs-on: ubuntu-latest
    steps:
    - name: All tests passed
      run: echo "All tests passed successfully!"
```

## Commands to Run

```bash
# Install shared dependencies
cd shared
uv venv
uv pip install -e ".[dev]"

# Run shared tests
uv run pytest -v --cov=models --cov=schemas

# Initialize Alembic (first time only)
uv run alembic init alembic

# Create initial migration
uv run alembic revision --autogenerate -m "Initial schema"

# Run migrations
uv run alembic upgrade head

# Update service dependencies
cd ../services/private
uv pip install -e "../../shared"

cd ../public  
uv pip install -e "../../shared"

# Run all tests
cd ../../
./scripts/test-all.sh
```

## Verification

1. All models can be instantiated and saved
2. Schema validation works correctly
3. Relationships between models work
4. Tests achieve ≥90% coverage
5. CI/CD passes with shared component tests

## Next Steps

After database models are complete and tested, proceed to Task 03: Core Configuration and Settings.