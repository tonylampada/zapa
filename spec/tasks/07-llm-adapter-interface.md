# Task 07: LLM Adapter Using OpenAI Agents SDK

## Objective
Implement the LLM adapter using the OpenAI Agents SDK (`openai-agents`) to provide intelligent agent capabilities with tool calling support for message search, summarization, and task extraction.

## Prerequisites
- Tasks 01-06 completed
- WhatsApp Bridge adapter working
- All previous tests passing in CI/CD

## Success Criteria
- [ ] Install and configure OpenAI Agents SDK
- [ ] Create Zapa Agent with proper instructions
- [ ] Implement agent tools for message operations
- [ ] Support multiple LLM providers via custom clients
- [ ] Unit tests with mocked agent responses
- [ ] Integration tests (skippable by default)
- [ ] Error handling and retry logic
- [ ] Tests passing locally and in CI/CD

## Implementation Plan

### 1. Add Dependencies

Update `backend/pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "openai-agents>=0.1.0",
]
```

### 2. Create Agent Tools

#### backend/app/adapters/llm/__init__.py
```python
"""LLM adapter using OpenAI Agents SDK."""
from .agent import ZapaAgent, create_agent
from .tools import (
    search_messages,
    get_recent_messages,
    summarize_chat,
    extract_tasks,
    get_conversation_stats,
)

__all__ = [
    "ZapaAgent",
    "create_agent",
    "search_messages",
    "get_recent_messages",
    "summarize_chat",
    "extract_tasks",
    "get_conversation_stats",
]
```

#### backend/app/adapters/llm/tools.py
```python
"""Agent tools for message operations."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from agents import function_tool, RunContextWrapper
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.models import Message, User
import logging

logger = logging.getLogger(__name__)


class MessageSearchResult(BaseModel):
    """Result from message search."""
    message_id: int
    content: str
    sender: str
    timestamp: datetime
    relevance_score: float = Field(default=1.0)


class ChatSummary(BaseModel):
    """Summary of a chat conversation."""
    summary: str
    message_count: int
    date_range: Dict[str, datetime]
    key_topics: List[str]


class ExtractedTask(BaseModel):
    """Task extracted from conversation."""
    task: str
    mentioned_at: datetime
    priority: str = Field(default="medium")
    completed: bool = Field(default=False)


class ConversationStats(BaseModel):
    """Statistics about a conversation."""
    total_messages: int
    user_messages: int
    assistant_messages: int
    date_range: Dict[str, datetime]
    average_messages_per_day: float


@function_tool
async def search_messages(
    ctx: RunContextWrapper[Dict[str, Any]],
    query: str,
    limit: int = 10,
) -> List[MessageSearchResult]:
    """
    Search through the user's message history.
    
    Args:
        query: Search query to find relevant messages
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        List of messages matching the search query
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")
    
    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return []
    
    try:
        # Simple text search - in production, use PostgreSQL full-text search
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .where(Message.content.ilike(f"%{query}%"))
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        return [
            MessageSearchResult(
                message_id=msg.id,
                content=msg.content,
                sender="user" if msg.is_from_user else "assistant",
                timestamp=msg.created_at,
            )
            for msg in messages
        ]
        
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        return []


@function_tool
async def get_recent_messages(
    ctx: RunContextWrapper[Dict[str, Any]],
    count: int = 20,
) -> List[MessageSearchResult]:
    """
    Get the most recent messages from the conversation.
    
    Args:
        count: Number of recent messages to retrieve (default: 20)
        
    Returns:
        List of recent messages in chronological order
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")
    
    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return []
    
    try:
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(count)
        )
        
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        # Reverse to get chronological order
        messages.reverse()
        
        return [
            MessageSearchResult(
                message_id=msg.id,
                content=msg.content,
                sender="user" if msg.is_from_user else "assistant",
                timestamp=msg.created_at,
            )
            for msg in messages
        ]
        
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return []


@function_tool
async def summarize_chat(
    ctx: RunContextWrapper[Dict[str, Any]],
    last_n_messages: int = 50,
) -> ChatSummary:
    """
    Generate a summary of recent conversation.
    
    Args:
        last_n_messages: Number of recent messages to summarize (default: 50)
        
    Returns:
        Summary of the conversation including key topics
    """
    # Get recent messages
    messages = await get_recent_messages(ctx, last_n_messages)
    
    if not messages:
        return ChatSummary(
            summary="No messages found to summarize.",
            message_count=0,
            date_range={},
            key_topics=[],
        )
    
    # Extract content for summary
    conversation_text = "\n".join([
        f"{msg.sender}: {msg.content}" for msg in messages
    ])
    
    # Simple summary (in production, use another LLM call)
    summary = f"Conversation between user and assistant covering {len(messages)} messages."
    
    # Extract date range
    date_range = {
        "start": messages[0].timestamp,
        "end": messages[-1].timestamp,
    }
    
    # Extract key topics (simple keyword extraction)
    # In production, use NLP techniques
    key_topics = ["general conversation"]
    
    return ChatSummary(
        summary=summary,
        message_count=len(messages),
        date_range=date_range,
        key_topics=key_topics,
    )


@function_tool
async def extract_tasks(
    ctx: RunContextWrapper[Dict[str, Any]],
    last_n_messages: int = 100,
) -> List[ExtractedTask]:
    """
    Extract actionable tasks mentioned in the conversation.
    
    Args:
        last_n_messages: Number of recent messages to analyze (default: 100)
        
    Returns:
        List of tasks mentioned in the conversation
    """
    messages = await get_recent_messages(ctx, last_n_messages)
    
    tasks = []
    
    # Simple task extraction - look for action words
    # In production, use NLP or another LLM call
    action_keywords = [
        "todo", "task", "remind", "need to", "should", 
        "must", "have to", "don't forget", "remember to"
    ]
    
    for msg in messages:
        content_lower = msg.content.lower()
        if any(keyword in content_lower for keyword in action_keywords):
            tasks.append(
                ExtractedTask(
                    task=msg.content[:100],  # First 100 chars
                    mentioned_at=msg.timestamp,
                    priority="medium",
                    completed=False,
                )
            )
    
    return tasks


@function_tool
async def get_conversation_stats(
    ctx: RunContextWrapper[Dict[str, Any]],
) -> ConversationStats:
    """
    Get statistics about the entire conversation history.
    
    Returns:
        Statistics including message counts and date ranges
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")
    
    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return ConversationStats(
            total_messages=0,
            user_messages=0,
            assistant_messages=0,
            date_range={},
            average_messages_per_day=0.0,
        )
    
    try:
        # Get total message count
        total_stmt = select(func.count(Message.id)).where(Message.user_id == user_id)
        total_result = await db.execute(total_stmt)
        total_messages = total_result.scalar() or 0
        
        # Get user message count
        user_stmt = (
            select(func.count(Message.id))
            .where(Message.user_id == user_id)
            .where(Message.is_from_user == True)
        )
        user_result = await db.execute(user_stmt)
        user_messages = user_result.scalar() or 0
        
        # Get date range
        date_stmt = (
            select(
                func.min(Message.created_at).label("first"),
                func.max(Message.created_at).label("last"),
            )
            .where(Message.user_id == user_id)
        )
        date_result = await db.execute(date_stmt)
        date_row = date_result.one_or_none()
        
        if date_row and date_row.first and date_row.last:
            date_range = {
                "start": date_row.first,
                "end": date_row.last,
            }
            
            # Calculate average messages per day
            days_diff = (date_row.last - date_row.first).days + 1
            avg_per_day = total_messages / days_diff if days_diff > 0 else 0
        else:
            date_range = {}
            avg_per_day = 0.0
        
        return ConversationStats(
            total_messages=total_messages,
            user_messages=user_messages,
            assistant_messages=total_messages - user_messages,
            date_range=date_range,
            average_messages_per_day=avg_per_day,
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        return ConversationStats(
            total_messages=0,
            user_messages=0,
            assistant_messages=0,
            date_range={},
            average_messages_per_day=0.0,
        )
```

#### backend/app/adapters/llm/agent.py
```python
"""Zapa Agent implementation using OpenAI Agents SDK."""
from typing import Dict, Any, Optional, List
from agents import Agent, Runner
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from .tools import (
    search_messages,
    get_recent_messages,
    summarize_chat,
    extract_tasks,
    get_conversation_stats,
)

logger = logging.getLogger(__name__)


class ZapaAgent:
    """WhatsApp agent with message history tools."""
    
    DEFAULT_INSTRUCTIONS = """You are a helpful WhatsApp assistant with access to the user's message history.
    
    You can:
    - Search through past messages
    - Retrieve recent conversations
    - Summarize chat history
    - Extract tasks from conversations
    - Provide conversation statistics
    
    Be conversational and helpful. When users ask about their message history, use the available tools to provide accurate information."""
    
    def __init__(
        self,
        name: str = "Zapa Assistant",
        instructions: Optional[str] = None,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize Zapa Agent.
        
        Args:
            name: Agent name
            instructions: Custom instructions (uses default if not provided)
            model: Model to use
            api_key: OpenAI API key (uses env var if not provided)
            base_url: Custom API base URL for OpenAI-compatible providers
            temperature: Sampling temperature
        """
        self.name = name
        self.instructions = instructions or self.DEFAULT_INSTRUCTIONS
        self.model = model
        self.temperature = temperature
        
        # Configure custom client if needed
        self.client = None
        if api_key or base_url:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        
        # Create agent with tools
        self.agent = Agent(
            name=self.name,
            instructions=self.instructions,
            model=self.model,
            tools=[
                search_messages,
                get_recent_messages,
                summarize_chat,
                extract_tasks,
                get_conversation_stats,
            ],
            temperature=self.temperature,
            client=self.client,
        )
    
    async def process_message(
        self,
        message: str,
        db_session: AsyncSession,
        user_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Process a user message and generate response.
        
        Args:
            message: User's message
            db_session: Database session for tools
            user_id: User ID for context
            conversation_history: Optional previous messages
            
        Returns:
            Agent's response
        """
        # Create context for tools
        context = {
            "db_session": db_session,
            "user_id": user_id,
        }
        
        # Build message list
        messages = []
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message,
        })
        
        try:
            # Run agent
            result = await Runner.run(
                self.agent,
                messages=messages,
                context=context,
            )
            
            return result.final_output
            
        except Exception as e:
            logger.error(f"Error processing message with agent: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again."
    
    def update_instructions(self, instructions: str):
        """Update agent instructions."""
        self.instructions = instructions
        self.agent.instructions = instructions
    
    def update_model(self, model: str):
        """Update the model used by the agent."""
        self.model = model
        self.agent.model = model


def create_agent(
    provider: str = "openai",
    api_key: str = None,
    model: str = None,
    **kwargs
) -> ZapaAgent:
    """
    Factory function to create agents for different providers.
    
    Args:
        provider: LLM provider (openai, anthropic, google, etc.)
        api_key: API key for the provider
        model: Model to use
        **kwargs: Additional provider-specific arguments
        
    Returns:
        Configured ZapaAgent instance
    """
    # Provider-specific configurations
    provider_configs = {
        "openai": {
            "base_url": None,
            "model": model or "gpt-4o",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "model": model or "claude-3-opus-20240229",
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": model or "gemini-pro",
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "model": model or "llama2",
        },
        # Add more providers as needed
    }
    
    config = provider_configs.get(provider, provider_configs["openai"])
    config.update(kwargs)
    
    return ZapaAgent(
        api_key=api_key,
        **config
    )
```

#### backend/app/adapters/llm/exceptions.py
```python
"""LLM adapter exceptions."""


class LLMError(Exception):
    """Base exception for LLM operations."""
    
    def __init__(self, message: str, provider: str = "unknown", original_error: Exception = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class LLMConnectionError(LLMError):
    """Raised when connection to LLM provider fails."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication with LLM provider fails."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class LLMInvalidRequestError(LLMError):
    """Raised when request to LLM is invalid."""
    pass
```

### 3. Create Tests

#### backend/tests/adapters/llm/test_tools.py
```python
"""Tests for agent tools."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.tools import (
    search_messages,
    get_recent_messages,
    summarize_chat,
    extract_tasks,
    get_conversation_stats,
    MessageSearchResult,
    ChatSummary,
    ExtractedTask,
    ConversationStats,
)
from app.models import Message, User


@pytest.fixture
def mock_context():
    """Create mock context for tools."""
    context = MagicMock()
    context.context = {
        "db_session": AsyncMock(spec=AsyncSession),
        "user_id": 1,
    }
    return context


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    now = datetime.utcnow()
    return [
        Message(
            id=1,
            user_id=1,
            content="Hello, I need help with a task",
            is_from_user=True,
            created_at=now - timedelta(hours=2),
        ),
        Message(
            id=2,
            user_id=1,
            content="Sure, I'd be happy to help. What do you need?",
            is_from_user=False,
            created_at=now - timedelta(hours=1.5),
        ),
        Message(
            id=3,
            user_id=1,
            content="I need to remember to buy groceries tomorrow",
            is_from_user=True,
            created_at=now - timedelta(hours=1),
        ),
        Message(
            id=4,
            user_id=1,
            content="I'll remind you about buying groceries tomorrow.",
            is_from_user=False,
            created_at=now - timedelta(minutes=30),
        ),
    ]


@pytest.mark.asyncio
async def test_search_messages(mock_context, sample_messages):
    """Test message search functionality."""
    # Mock database query
    db = mock_context.context["db_session"]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_messages[2]]
    db.execute.return_value = mock_result
    
    # Search for "groceries"
    results = await search_messages(mock_context, "groceries", limit=5)
    
    assert len(results) == 1
    assert isinstance(results[0], MessageSearchResult)
    assert "groceries" in results[0].content
    assert results[0].sender == "user"


@pytest.mark.asyncio
async def test_get_recent_messages(mock_context, sample_messages):
    """Test getting recent messages."""
    # Mock database query
    db = mock_context.context["db_session"]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = sample_messages[-2:]
    db.execute.return_value = mock_result
    
    # Get recent messages
    results = await get_recent_messages(mock_context, count=2)
    
    assert len(results) == 2
    assert results[0].message_id == 3
    assert results[1].message_id == 4


@pytest.mark.asyncio
async def test_summarize_chat(mock_context, sample_messages):
    """Test chat summarization."""
    # Mock get_recent_messages to return sample data
    mock_messages = [
        MessageSearchResult(
            message_id=msg.id,
            content=msg.content,
            sender="user" if msg.is_from_user else "assistant",
            timestamp=msg.created_at,
        )
        for msg in sample_messages
    ]
    
    # Patch get_recent_messages
    import app.adapters.llm.tools
    original_func = app.adapters.llm.tools.get_recent_messages
    app.adapters.llm.tools.get_recent_messages = AsyncMock(return_value=mock_messages)
    
    try:
        summary = await summarize_chat(mock_context, last_n_messages=50)
        
        assert isinstance(summary, ChatSummary)
        assert summary.message_count == 4
        assert "start" in summary.date_range
        assert "end" in summary.date_range
        assert len(summary.key_topics) > 0
        
    finally:
        app.adapters.llm.tools.get_recent_messages = original_func


@pytest.mark.asyncio
async def test_extract_tasks(mock_context, sample_messages):
    """Test task extraction."""
    # Mock get_recent_messages
    mock_messages = [
        MessageSearchResult(
            message_id=msg.id,
            content=msg.content,
            sender="user" if msg.is_from_user else "assistant",
            timestamp=msg.created_at,
        )
        for msg in sample_messages
    ]
    
    import app.adapters.llm.tools
    original_func = app.adapters.llm.tools.get_recent_messages
    app.adapters.llm.tools.get_recent_messages = AsyncMock(return_value=mock_messages)
    
    try:
        tasks = await extract_tasks(mock_context, last_n_messages=100)
        
        assert len(tasks) >= 1
        assert any("groceries" in task.task for task in tasks)
        assert all(isinstance(task, ExtractedTask) for task in tasks)
        
    finally:
        app.adapters.llm.tools.get_recent_messages = original_func


@pytest.mark.asyncio
async def test_get_conversation_stats(mock_context):
    """Test conversation statistics."""
    db = mock_context.context["db_session"]
    
    # Mock count queries
    db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=100)),  # Total messages
        MagicMock(scalar=MagicMock(return_value=60)),   # User messages
        MagicMock(one_or_none=MagicMock(return_value=MagicMock(
            first=datetime.utcnow() - timedelta(days=10),
            last=datetime.utcnow(),
        ))),  # Date range
    ]
    
    stats = await get_conversation_stats(mock_context)
    
    assert isinstance(stats, ConversationStats)
    assert stats.total_messages == 100
    assert stats.user_messages == 60
    assert stats.assistant_messages == 40
    assert stats.average_messages_per_day == pytest.approx(9.09, rel=0.1)


@pytest.mark.asyncio
async def test_tools_with_missing_context(mock_context):
    """Test tools handle missing context gracefully."""
    # Remove required context
    mock_context.context = {}
    
    # All tools should return empty/default results
    search_results = await search_messages(mock_context, "test")
    assert search_results == []
    
    recent_results = await get_recent_messages(mock_context, 10)
    assert recent_results == []
    
    stats = await get_conversation_stats(mock_context)
    assert stats.total_messages == 0
```

#### backend/tests/adapters/llm/test_agent.py
```python
"""Tests for Zapa Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.agent import ZapaAgent, create_agent


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initialization with default settings."""
    agent = ZapaAgent()
    
    assert agent.name == "Zapa Assistant"
    assert agent.model == "gpt-4o"
    assert agent.temperature == 0.7
    assert "WhatsApp assistant" in agent.instructions
    assert len(agent.agent.tools) == 5  # All tools registered


@pytest.mark.asyncio
async def test_agent_custom_initialization():
    """Test agent with custom settings."""
    custom_instructions = "You are a specialized bot."
    agent = ZapaAgent(
        name="Custom Bot",
        instructions=custom_instructions,
        model="gpt-3.5-turbo",
        temperature=0.5,
    )
    
    assert agent.name == "Custom Bot"
    assert agent.instructions == custom_instructions
    assert agent.model == "gpt-3.5-turbo"
    assert agent.temperature == 0.5


@pytest.mark.asyncio
async def test_process_message_success(mock_db_session):
    """Test successful message processing."""
    agent = ZapaAgent()
    
    # Mock Runner.run
    with patch("app.adapters.llm.agent.Runner") as mock_runner:
        mock_result = MagicMock()
        mock_result.final_output = "Hello! How can I help you today?"
        mock_runner.run.return_value = mock_result
        
        response = await agent.process_message(
            message="Hello",
            db_session=mock_db_session,
            user_id=1,
        )
        
        assert response == "Hello! How can I help you today?"
        mock_runner.run.assert_called_once()
        
        # Check context was passed correctly
        call_args = mock_runner.run.call_args
        context = call_args.kwargs["context"]
        assert context["db_session"] == mock_db_session
        assert context["user_id"] == 1


@pytest.mark.asyncio
async def test_process_message_with_history(mock_db_session):
    """Test message processing with conversation history."""
    agent = ZapaAgent()
    
    conversation_history = [
        {"role": "user", "content": "What's the weather?"},
        {"role": "assistant", "content": "I can't check weather, but I can help with your messages."},
    ]
    
    with patch("app.adapters.llm.agent.Runner") as mock_runner:
        mock_result = MagicMock()
        mock_result.final_output = "Based on our conversation..."
        mock_runner.run.return_value = mock_result
        
        response = await agent.process_message(
            message="What did we talk about?",
            db_session=mock_db_session,
            user_id=1,
            conversation_history=conversation_history,
        )
        
        assert response == "Based on our conversation..."
        
        # Check messages were built correctly
        call_args = mock_runner.run.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 3  # 2 history + 1 current
        assert messages[0]["content"] == "What's the weather?"
        assert messages[2]["content"] == "What did we talk about?"


@pytest.mark.asyncio
async def test_process_message_error_handling(mock_db_session):
    """Test error handling in message processing."""
    agent = ZapaAgent()
    
    with patch("app.adapters.llm.agent.Runner") as mock_runner:
        mock_runner.run.side_effect = Exception("API Error")
        
        response = await agent.process_message(
            message="Hello",
            db_session=mock_db_session,
            user_id=1,
        )
        
        assert "encountered an error" in response


def test_update_instructions():
    """Test updating agent instructions."""
    agent = ZapaAgent()
    new_instructions = "You are now a different assistant."
    
    agent.update_instructions(new_instructions)
    
    assert agent.instructions == new_instructions
    assert agent.agent.instructions == new_instructions


def test_update_model():
    """Test updating agent model."""
    agent = ZapaAgent()
    new_model = "gpt-3.5-turbo"
    
    agent.update_model(new_model)
    
    assert agent.model == new_model
    assert agent.agent.model == new_model


def test_create_agent_openai():
    """Test creating OpenAI agent."""
    agent = create_agent(
        provider="openai",
        api_key="test-key",
        model="gpt-4",
    )
    
    assert isinstance(agent, ZapaAgent)
    assert agent.model == "gpt-4"
    assert agent.client is not None


def test_create_agent_anthropic():
    """Test creating Anthropic agent."""
    agent = create_agent(
        provider="anthropic",
        api_key="test-key",
    )
    
    assert isinstance(agent, ZapaAgent)
    assert agent.model == "claude-3-opus-20240229"
    assert agent.client is not None
    assert "anthropic.com" in agent.client.base_url


def test_create_agent_custom_provider():
    """Test creating agent with custom provider."""
    agent = create_agent(
        provider="custom",
        api_key="test-key",
        base_url="https://custom-api.com/v1",
        model="custom-model",
    )
    
    assert isinstance(agent, ZapaAgent)
    assert agent.model == "custom-model"
    assert agent.client is not None
```

### 4. Integration Tests

#### backend/tests/adapters/llm/test_agent_integration.py
```python
"""Integration tests for Zapa Agent."""
import pytest
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.agent import create_agent
from app.models import User, Message
from tests.fixtures import TestDatabaseManager


# Skip integration tests by default
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_LLM", "false").lower() != "true",
    reason="LLM integration tests disabled. Set INTEGRATION_TEST_LLM=true to run."
)


@pytest.fixture
async def test_db():
    """Create test database with sample data."""
    async with TestDatabaseManager() as manager:
        async with manager.get_session() as session:
            # Create test user
            user = User(
                phone_number="+1234567890",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            
            # Create sample messages
            messages = [
                Message(
                    user_id=user.id,
                    content="Hello, I need to remember to call John tomorrow",
                    is_from_user=True,
                ),
                Message(
                    user_id=user.id,
                    content="I'll help you remember to call John tomorrow.",
                    is_from_user=False,
                ),
                Message(
                    user_id=user.id,
                    content="Also, remind me to buy milk and eggs",
                    is_from_user=True,
                ),
            ]
            
            session.add_all(messages)
            await session.commit()
            
            yield session, user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_agent_simple_response(test_db):
    """Test real agent with simple response."""
    session, user_id = test_db
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    agent = create_agent(
        provider="openai",
        api_key=api_key,
        model="gpt-3.5-turbo",
    )
    
    response = await agent.process_message(
        message="Hello, how are you?",
        db_session=session,
        user_id=user_id,
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    # Response should be friendly
    assert any(word in response.lower() for word in ["hello", "hi", "help", "assist"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_agent_search_messages(test_db):
    """Test real agent searching through messages."""
    session, user_id = test_db
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    agent = create_agent(
        provider="openai",
        api_key=api_key,
        model="gpt-3.5-turbo",
    )
    
    response = await agent.process_message(
        message="Did I mention anything about John?",
        db_session=session,
        user_id=user_id,
    )
    
    assert isinstance(response, str)
    assert "john" in response.lower()
    assert "call" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_agent_extract_tasks(test_db):
    """Test real agent extracting tasks."""
    session, user_id = test_db
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    agent = create_agent(
        provider="openai",
        api_key=api_key,
        model="gpt-3.5-turbo",
    )
    
    response = await agent.process_message(
        message="What tasks do I have pending?",
        db_session=session,
        user_id=user_id,
    )
    
    assert isinstance(response, str)
    # Should mention the tasks
    assert any(task in response.lower() for task in ["john", "milk", "eggs"])
```

## Commands to Run

```bash
# Install dependencies
cd backend
pip install -e ".[dev]"

# Run unit tests
pytest tests/adapters/llm/test_tools.py -v
pytest tests/adapters/llm/test_agent.py -v

# Run integration tests (requires API key)
INTEGRATION_TEST_LLM=true OPENAI_API_KEY=sk-... pytest tests/adapters/llm/test_agent_integration.py -v

# Run all LLM adapter tests
pytest tests/adapters/llm/ -v --cov=app.adapters.llm

# Linting and formatting
black app/adapters/llm/ tests/adapters/llm/
ruff check app/adapters/llm/ tests/adapters/llm/
mypy app/adapters/llm/
```

## Verification

1. OpenAI Agents SDK properly integrated
2. All agent tools work with database context
3. Support for multiple LLM providers via custom clients
4. Unit tests cover all functionality
5. Integration tests verify real agent behavior
6. Error handling for API failures
7. Code coverage ≥ 90%

## Configuration

The agent can be configured in multiple ways:

1. **Environment Variables** (default):
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Direct Configuration**:
   ```python
   agent = create_agent(
       provider="openai",
       api_key="sk-...",
       model="gpt-4o",
   )
   ```

3. **Custom Provider**:
   ```python
   agent = create_agent(
       provider="custom",
       api_key="key",
       base_url="https://custom-llm-api.com/v1",
       model="custom-model",
   )
   ```

## Next Steps

After the LLM adapter is complete, proceed to Task 08: Message Service and Storage.