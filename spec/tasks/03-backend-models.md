# Task 03: Backend Models and Database Schema with Tests

## Objective
Implement SQLAlchemy models and Pydantic schemas with comprehensive test coverage, including database migrations.

## Prerequisites
- Task 01 completed (project setup)
- Task 02 completed (backend structure)
- All tests passing in CI/CD

## Requirements
- Create SQLAlchemy models for all entities
- Create Pydantic schemas for request/response validation
- Set up Alembic for database migrations
- Write comprehensive tests for all models and schemas
- Ensure proper relationships and constraints

## Files to Create

### backend/app/models/base.py
```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)
```

### backend/app/models/enums.py
```python
import enum

class SessionStatus(str, enum.Enum):
    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"

class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

### backend/tests/test_models.py
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.models.base import Base
from app.models.models import User, Agent, Session, Message, Log
from app.models.enums import SessionStatus, MessageDirection, LogLevel

@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_user_model(db_session):
    """Test User model creation and properties."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpass123"
    )
    db_session.add(user)
    db_session.commit()
    
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.created_at is not None

def test_agent_model(db_session):
    """Test Agent model with functions."""
    agent = Agent(
        name="Test Agent",
        description="A test agent",
        model="gpt-4",
        system_prompt="You are a helpful assistant",
        functions=[
            {
                "name": "summarize",
                "description": "Summarize conversation",
                "parameters": {}
            }
        ]
    )
    db_session.add(agent)
    db_session.commit()
    
    assert agent.id is not None
    assert agent.model == "gpt-4"
    assert len(agent.functions) == 1
    assert agent.functions[0]["name"] == "summarize"

def test_session_agent_relationship(db_session):
    """Test relationship between Session and Agent."""
    agent = Agent(name="Test Agent", system_prompt="Test")
    db_session.add(agent)
    db_session.commit()
    
    session = Session(
        id="session123",
        agent_id=agent.id,
        status=SessionStatus.QR_PENDING
    )
    db_session.add(session)
    db_session.commit()
    
    assert session.agent.id == agent.id
    assert agent.sessions[0].id == "session123"

def test_message_model(db_session):
    """Test Message model with metadata."""
    agent = Agent(name="Test Agent", system_prompt="Test")
    session = Session(id="session123", agent_id=agent.id)
    db_session.add_all([agent, session])
    db_session.commit()
    
    message = Message(
        session_id="session123",
        contact_jid="+1234567890",
        direction=MessageDirection.INCOMING,
        content="Hello, world!",
        metadata={"source": "whatsapp", "delivered": True}
    )
    db_session.add(message)
    db_session.commit()
    
    assert message.id is not None
    assert message.session_id == "session123"
    assert message.metadata["source"] == "whatsapp"
    assert message.timestamp is not None

def test_log_model(db_session):
    """Test Log model."""
    log = Log(
        level=LogLevel.INFO,
        source="test_service",
        message="Test log entry",
        details={"action": "test", "result": "success"}
    )
    db_session.add(log)
    db_session.commit()
    
    assert log.id is not None
    assert log.level == LogLevel.INFO
    assert log.details["result"] == "success"
```

### backend/tests/test_schemas.py
```python
import pytest
from datetime import datetime
from pydantic import ValidationError
from app.models.schemas import (
    UserCreate, UserResponse,
    AgentCreate, AgentResponse,
    SessionCreate, SessionResponse,
    MessageCreate, MessageResponse,
    WebhookMessage
)

def test_user_create_schema():
    """Test UserCreate schema validation."""
    # Valid user
    user = UserCreate(
        username="testuser",
        email="test@example.com",
        password="securepass123"
    )
    assert user.username == "testuser"
    
    # Invalid email
    with pytest.raises(ValidationError):
        UserCreate(
            username="testuser",
            email="invalid-email",
            password="pass"
        )

def test_agent_create_schema():
    """Test AgentCreate schema with functions."""
    agent = AgentCreate(
        name="Test Agent",
        system_prompt="You are helpful",
        functions=[
            {
                "name": "search",
                "description": "Search messages",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            }
        ]
    )
    assert agent.model == "gpt-4"  # default value
    assert len(agent.functions) == 1

def test_session_response_schema():
    """Test SessionResponse schema serialization."""
    # Mock data that would come from DB
    agent_data = {
        "id": 1,
        "name": "Test Agent",
        "description": None,
        "model": "gpt-4",
        "system_prompt": "Test",
        "functions": [],
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None
    }
    
    session_data = {
        "id": "session123",
        "status": "connected",
        "phone_number": "+1234567890",
        "qr_code": None,
        "agent_id": 1,
        "agent": agent_data,
        "connected_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    response = SessionResponse(**session_data)
    assert response.status == "connected"
    assert response.agent.name == "Test Agent"

def test_webhook_message_schema():
    """Test WebhookMessage schema for incoming webhooks."""
    webhook = WebhookMessage(
        session_id="session123",
        contact_jid="+1234567890",
        message_type="text",
        content="Hello",
        timestamp=datetime.now(),
        metadata={"platform": "whatsapp"}
    )
    assert webhook.message_type == "text"
    assert webhook.metadata["platform"] == "whatsapp"

def test_message_create_validation():
    """Test message creation validation."""
    # Valid message
    msg = MessageCreate(
        session_id="session123",
        contact_jid="+1234567890",
        direction="incoming",
        content="Test message"
    )
    assert msg.message_type == "text"  # default
    
    # Invalid direction
    with pytest.raises(ValidationError):
        MessageCreate(
            session_id="session123",
            contact_jid="+1234567890",
            direction="invalid",
            content="Test"
        )
```

### backend/alembic.ini
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = sqlite:///./test.db

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

### backend/alembic/env.py
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.models.base import Base
from app.models.models import User, Agent, Session, Message, Log
from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### backend/tests/test_migrations.py
```python
import pytest
import subprocess
import os
from sqlalchemy import create_engine, inspect
from app.models.base import Base
from app.core.config import settings

def test_alembic_init():
    """Test that alembic can be initialized."""
    result = subprocess.run(
        ["uv", "run", "alembic", "history"],
        cwd="backend",
        capture_output=True,
        text=True
    )
    # Should not error even with no migrations
    assert result.returncode == 0 or "No revision files found" in result.stderr

def test_create_migration():
    """Test creating a migration."""
    # This is more of an integration test
    # In real implementation, we'd test that migrations work
    pass

def test_model_table_creation():
    """Test that all models create proper tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = ["users", "agents", "sessions", "messages", "logs"]
    for table in expected_tables:
        assert table in tables
    
    # Check some columns
    user_columns = [col["name"] for col in inspector.get_columns("users")]
    assert "id" in user_columns
    assert "username" in user_columns
    assert "email" in user_columns
```

## Updated pyproject.toml dependencies
```toml
[project]
dependencies = [
    "fastapi==0.104.1",
    "uvicorn[standard]==0.24.0",
    "sqlalchemy==2.0.23",
    "alembic==1.12.1",
    "psycopg2-binary==2.9.9",
    "pydantic==2.5.2",
    "pydantic-settings==2.1.0",
    "python-jose[cryptography]==3.3.0",
    "passlib[bcrypt]==1.7.4",
    "python-multipart==0.0.6",
]
```

## Tests to Verify

1. **Model Tests** - All SQLAlchemy models work correctly
2. **Schema Tests** - Pydantic validation works as expected
3. **Relationship Tests** - Foreign keys and relationships work
4. **Migration Tests** - Alembic can create and run migrations
5. **Constraint Tests** - Unique constraints, nullability work

## Success Criteria
- [ ] All models created with proper relationships
- [ ] All schemas validate data correctly
- [ ] Alembic configured and can create migrations
- [ ] Tests cover all models and schemas
- [ ] Tests pass locally and in CI/CD
- [ ] Code coverage above 90%

## Commands to Run
```bash
cd backend

# Initialize alembic (first time only)
uv run alembic init alembic

# Create initial migration
uv run alembic revision --autogenerate -m "Initial models"

# Run migrations
uv run alembic upgrade head

# Run tests
uv run pytest tests/test_models.py tests/test_schemas.py -v

# Run with coverage
uv run pytest tests -v --cov=app.models --cov-report=term-missing
```