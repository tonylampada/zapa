# Task 04: Backend Adapters Implementation with Tests

## Objective
Implement adapter layer for external service integrations with comprehensive mocking and testing strategies.

## Prerequisites
- Tasks 01-03 completed
- All previous tests passing in CI/CD

## Requirements
- Create adapters for WhatsApp Bridge, OpenAI, and Database
- Write comprehensive tests using mocks for external services
- Implement retry logic and error handling
- Create integration test fixtures

## Files to Create

### backend/app/adapters/base.py
```python
from typing import TypeVar, Generic, Optional
from abc import ABC, abstractmethod

T = TypeVar('T')

class BaseAdapter(ABC):
    """Base class for all adapters."""
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the service is healthy."""
        pass

class RetryConfig:
    """Configuration for retry logic."""
    def __init__(self, max_attempts: int = 3, backoff_factor: float = 2.0):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
```

### backend/tests/test_whatsapp_adapter.py
```python
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.adapters.whatsapp_client import WhatsAppClient

@pytest.fixture
def whatsapp_client():
    """Create WhatsApp client instance."""
    return WhatsAppClient()

@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    with patch('httpx.AsyncClient') as mock:
        yield mock

@pytest.mark.asyncio
async def test_create_session_success(whatsapp_client, mock_httpx_client):
    """Test successful session creation."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "id": "session123",
        "qr_code": "data:image/png;base64,..."
    }
    mock_response.raise_for_status.return_value = None
    
    # Configure mock client
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
    
    # Test
    result = await whatsapp_client.create_session("session123")
    
    assert result["id"] == "session123"
    assert "qr_code" in result
    mock_client_instance.post.assert_called_once()

@pytest.mark.asyncio
async def test_create_session_error(whatsapp_client, mock_httpx_client):
    """Test session creation with error."""
    # Mock error response
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=None, response=mock_response
    )
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
    
    # Test
    with pytest.raises(httpx.HTTPStatusError):
        await whatsapp_client.create_session("session123")

@pytest.mark.asyncio
async def test_send_message_success(whatsapp_client, mock_httpx_client):
    """Test sending message successfully."""
    mock_response = AsyncMock()
    mock_response.json.return_value = {"message_id": "msg123", "status": "sent"}
    mock_response.raise_for_status.return_value = None
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
    
    result = await whatsapp_client.send_message(
        "session123", "+1234567890", "Hello!"
    )
    
    assert result["message_id"] == "msg123"
    assert result["status"] == "sent"

@pytest.mark.asyncio
async def test_delete_session(whatsapp_client, mock_httpx_client):
    """Test session deletion."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    mock_client_instance = AsyncMock()
    mock_client_instance.delete.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
    
    result = await whatsapp_client.delete_session("session123")
    assert result is True
    
    # Test failed deletion
    mock_response.status_code = 404
    result = await whatsapp_client.delete_session("nonexistent")
    assert result is False

@pytest.mark.asyncio
async def test_health_check(whatsapp_client, mock_httpx_client):
    """Test health check functionality."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
    
    result = await whatsapp_client.health_check()
    assert result is True
```

### backend/tests/test_openai_adapter.py
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from app.adapters.openai_client import OpenAIClient

@pytest.fixture
def openai_client():
    """Create OpenAI client instance."""
    return OpenAIClient()

@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch('openai.AsyncOpenAI') as mock:
        yield mock

@pytest.mark.asyncio
async def test_generate_chat_completion_simple(openai_client, mock_openai):
    """Test simple chat completion without functions."""
    # Mock response
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello! How can I help?"
    mock_choice.message.role = "assistant"
    mock_choice.finish_reason = "stop"
    mock_choice.message.function_call = None
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    # Configure mock
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    # Reinitialize client to use mocked OpenAI
    client = OpenAIClient()
    
    # Test
    result = await client.generate_chat_completion(
        messages=[{"role": "user", "content": "Hello"}]
    )
    
    assert result["content"] == "Hello! How can I help?"
    assert result["role"] == "assistant"
    assert "function_call" not in result

@pytest.mark.asyncio
async def test_generate_chat_completion_with_function(openai_client, mock_openai):
    """Test chat completion with function calling."""
    # Mock function call response
    mock_function_call = MagicMock()
    mock_function_call.name = "summarize_chat"
    mock_function_call.arguments = json.dumps({"last_n": 10})
    
    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.message.role = "assistant"
    mock_choice.finish_reason = "function_call"
    mock_choice.message.function_call = mock_function_call
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    # Configure mock
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    client = OpenAIClient()
    
    # Test
    functions = [{
        "name": "summarize_chat",
        "description": "Summarize the chat",
        "parameters": {"type": "object", "properties": {}}
    }]
    
    result = await client.generate_chat_completion(
        messages=[{"role": "user", "content": "Summarize our chat"}],
        functions=functions
    )
    
    assert result["function_call"]["name"] == "summarize_chat"
    assert json.loads(result["function_call"]["arguments"])["last_n"] == 10

@pytest.mark.asyncio
async def test_create_embedding(openai_client, mock_openai):
    """Test embedding creation."""
    # Mock embedding response
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    
    # Configure mock
    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    client = OpenAIClient()
    
    # Test
    result = await client.create_embedding("Test text")
    
    assert isinstance(result, list)
    assert len(result) == 5
    assert result[0] == 0.1

@pytest.mark.asyncio
async def test_moderate_content(openai_client, mock_openai):
    """Test content moderation."""
    # Mock moderation response
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "flagged": False,
        "categories": {
            "hate": False,
            "violence": False
        }
    }
    
    mock_response = MagicMock()
    mock_response.results = [mock_result]
    
    # Configure mock
    mock_client = AsyncMock()
    mock_client.moderations.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    client = OpenAIClient()
    
    # Test
    result = await client.moderate_content("This is a test message")
    
    assert result["flagged"] is False
    assert result["categories"]["hate"] is False

@pytest.mark.asyncio
async def test_openai_error_handling(openai_client, mock_openai):
    """Test error handling for OpenAI API errors."""
    # Configure mock to raise error
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    mock_openai.return_value = mock_client
    
    client = OpenAIClient()
    
    # Test
    with pytest.raises(Exception) as exc_info:
        await client.generate_chat_completion(
            messages=[{"role": "user", "content": "Test"}]
        )
    
    assert "API Error" in str(exc_info.value)
```

### backend/tests/test_db_repository.py
```python
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.models import User, Agent, Session, Message, Log
from app.models.enums import SessionStatus, MessageDirection, LogLevel
from app.adapters.db_repository import (
    UserRepository, AgentRepository, SessionRepository,
    MessageRepository, LogRepository
)

@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_user_repository(db_session):
    """Test UserRepository operations."""
    repo = UserRepository(db_session)
    
    # Create user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpass"
    )
    created_user = repo.create(user)
    assert created_user.id is not None
    
    # Get by username
    found_user = repo.get_by_username("testuser")
    assert found_user is not None
    assert found_user.email == "test@example.com"
    
    # Get by email
    found_user = repo.get_by_email("test@example.com")
    assert found_user is not None
    assert found_user.username == "testuser"
    
    # Not found
    assert repo.get_by_username("nonexistent") is None

def test_agent_repository(db_session):
    """Test AgentRepository operations."""
    repo = AgentRepository(db_session)
    
    # Create agents
    agent1 = Agent(name="Agent 1", system_prompt="Prompt 1")
    agent2 = Agent(name="Agent 2", system_prompt="Prompt 2", is_active=False)
    
    repo.create(agent1)
    repo.create(agent2)
    
    # Get all (only active)
    agents = repo.get_all()
    assert len(agents) == 1
    assert agents[0].name == "Agent 1"
    
    # Get by id
    found = repo.get_by_id(agent1.id)
    assert found is not None
    assert found.name == "Agent 1"
    
    # Update
    agent1.description = "Updated description"
    updated = repo.update(agent1)
    assert updated.description == "Updated description"

def test_session_repository(db_session):
    """Test SessionRepository operations."""
    agent_repo = AgentRepository(db_session)
    session_repo = SessionRepository(db_session)
    
    # Create agent first
    agent = agent_repo.create(Agent(name="Test Agent", system_prompt="Test"))
    
    # Create sessions
    session1 = Session(id="s1", agent_id=agent.id, status=SessionStatus.CONNECTED)
    session2 = Session(id="s2", agent_id=agent.id, status=SessionStatus.QR_PENDING)
    
    session_repo.create(session1)
    session_repo.create(session2)
    
    # Get all
    sessions = session_repo.get_all()
    assert len(sessions) == 2
    
    # Get active
    active = session_repo.get_active_sessions()
    assert len(active) == 1
    assert active[0].id == "s1"
    
    # Update
    session1.phone_number = "+1234567890"
    updated = session_repo.update(session1)
    assert updated.phone_number == "+1234567890"
    
    # Delete
    result = session_repo.delete("s2")
    assert result is True
    assert len(session_repo.get_all()) == 1

def test_message_repository(db_session):
    """Test MessageRepository operations."""
    # Setup
    agent_repo = AgentRepository(db_session)
    session_repo = SessionRepository(db_session)
    message_repo = MessageRepository(db_session)
    
    agent = agent_repo.create(Agent(name="Test Agent", system_prompt="Test"))
    session = session_repo.create(Session(id="s1", agent_id=agent.id))
    
    # Create messages
    for i in range(5):
        msg = Message(
            session_id="s1",
            contact_jid="+1234567890",
            direction=MessageDirection.INCOMING if i % 2 == 0 else MessageDirection.OUTGOING,
            content=f"Message {i}"
        )
        message_repo.create(msg)
    
    # Get conversation
    messages = message_repo.get_conversation("s1", "+1234567890", limit=3)
    assert len(messages) == 3
    
    # Get recent
    recent = message_repo.get_recent_messages("s1", "+1234567890", last_n=2)
    assert len(recent) == 2
    
    # Search
    msg_with_keyword = Message(
        session_id="s1",
        contact_jid="+1234567890",
        direction=MessageDirection.INCOMING,
        content="Special keyword here"
    )
    message_repo.create(msg_with_keyword)
    
    results = message_repo.search_messages("s1", "keyword")
    assert len(results) >= 1
    assert "keyword" in results[0].content

def test_log_repository(db_session):
    """Test LogRepository operations."""
    repo = LogRepository(db_session)
    
    # Create logs
    logs = [
        Log(level=LogLevel.INFO, source="test", message="Info log"),
        Log(level=LogLevel.ERROR, source="test", message="Error log", session_id="s1"),
        Log(level=LogLevel.WARNING, source="test", message="Warning log"),
    ]
    
    for log in logs:
        repo.create(log)
    
    # Get recent
    recent = repo.get_recent_logs(limit=2)
    assert len(recent) == 2
    
    # Filter by level
    errors = repo.get_recent_logs(level=LogLevel.ERROR)
    assert len(errors) == 1
    assert errors[0].message == "Error log"
    
    # Filter by session
    session_logs = repo.get_recent_logs(session_id="s1")
    assert len(session_logs) == 1
```

### backend/tests/test_vector_store.py
```python
import pytest
import numpy as np
from app.adapters.vector_store import VectorStore

def test_vector_store_basic():
    """Test basic vector store operations."""
    store = VectorStore()
    
    # Add vectors
    store.add_vector("vec1", [0.1, 0.2, 0.3], {"text": "Hello"})
    store.add_vector("vec2", [0.2, 0.3, 0.4], {"text": "World"})
    store.add_vector("vec3", [0.9, 0.8, 0.7], {"text": "Different"})
    
    # Search
    results = store.search([0.15, 0.25, 0.35], top_k=2)
    
    assert len(results) == 2
    assert results[0][0] in ["vec1", "vec2"]  # Should be similar to query
    assert results[0][1] > results[1][1]  # First result more similar
    
    # Delete
    store.delete_vector("vec1")
    results = store.search([0.1, 0.2, 0.3], top_k=3)
    assert len(results) == 2  # Only 2 vectors left

def test_vector_similarity():
    """Test vector similarity calculation."""
    store = VectorStore()
    
    # Add identical vector
    store.add_vector("same", [1.0, 0.0, 0.0])
    results = store.search([1.0, 0.0, 0.0], top_k=1)
    
    assert results[0][0] == "same"
    assert abs(results[0][1] - 1.0) < 0.0001  # Should be ~1.0 (perfect match)
    
    # Add orthogonal vector
    store.add_vector("orthogonal", [0.0, 1.0, 0.0])
    results = store.search([1.0, 0.0, 0.0], top_k=2)
    
    # Orthogonal vectors should have similarity ~0
    orthogonal_result = next(r for r in results if r[0] == "orthogonal")
    assert abs(orthogonal_result[1]) < 0.0001

def test_empty_vector_store():
    """Test searching in empty store."""
    store = VectorStore()
    results = store.search([0.1, 0.2, 0.3], top_k=5)
    assert len(results) == 0
```

## Integration Test Fixtures

### backend/tests/fixtures/mock_services.py
```python
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock

class MockWhatsAppService:
    """Mock WhatsApp service for integration tests."""
    
    def __init__(self):
        self.sessions = {}
        self.messages = []
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        self.sessions[session_id] = {
            "id": session_id,
            "status": "qr_pending",
            "qr_code": f"mock_qr_{session_id}"
        }
        return self.sessions[session_id]
    
    async def send_message(self, session_id: str, to: str, message: str) -> Dict[str, Any]:
        msg = {
            "id": f"msg_{len(self.messages)}",
            "session_id": session_id,
            "to": to,
            "message": message,
            "status": "sent"
        }
        self.messages.append(msg)
        return msg

class MockOpenAIService:
    """Mock OpenAI service for integration tests."""
    
    async def generate_chat_completion(self, messages, **kwargs):
        # Simple mock response based on last message
        last_msg = messages[-1]["content"].lower()
        
        if "summarize" in last_msg:
            return {
                "content": "This is a summary of the conversation.",
                "role": "assistant"
            }
        elif "hello" in last_msg:
            return {
                "content": "Hello! How can I help you?",
                "role": "assistant"
            }
        else:
            return {
                "content": "I understand. How can I assist you?",
                "role": "assistant"
            }
    
    async def create_embedding(self, text: str):
        # Return deterministic embedding based on text length
        length = len(text)
        return [0.1 * i for i in range(5)]
```

## Success Criteria
- [ ] All adapters implemented with proper error handling
- [ ] Comprehensive tests with mocks for external services
- [ ] Integration test fixtures created
- [ ] Retry logic implemented where appropriate
- [ ] Tests pass locally and in CI/CD
- [ ] Code coverage above 90%

## Commands to Run
```bash
cd backend

# Run adapter tests
uv run pytest tests/test_whatsapp_adapter.py -v
uv run pytest tests/test_openai_adapter.py -v
uv run pytest tests/test_db_repository.py -v
uv run pytest tests/test_vector_store.py -v

# Run all tests with coverage
uv run pytest tests -v --cov=app.adapters --cov-report=term-missing

# Run specific test
uv run pytest tests/test_whatsapp_adapter.py::test_create_session_success -v
```