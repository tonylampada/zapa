"""Tests for agent tools."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.tools import (
    ChatSummary,
    ConversationStats,
    ExtractedTask,
    MessageSearchResult,
    extract_tasks_impl,
    get_conversation_stats_impl,
    get_recent_messages_impl,
    search_messages_impl,
    summarize_chat_impl,
)
from app.models import Message


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
    results = await search_messages_impl(mock_context, "groceries", limit=5)

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
    # Get the last 2 messages in reverse order (newest first) as the DB would return them
    mock_messages = [sample_messages[3], sample_messages[2]]  # [message 4, message 3]
    mock_result.scalars.return_value.all.return_value = mock_messages
    db.execute.return_value = mock_result

    # Get recent messages
    results = await get_recent_messages_impl(mock_context, count=2)

    assert len(results) == 2
    # Results should be in chronological order (oldest first)
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

    # Patch get_recent_messages_impl
    import app.adapters.llm.tools

    original_func = app.adapters.llm.tools.get_recent_messages_impl
    app.adapters.llm.tools.get_recent_messages_impl = AsyncMock(return_value=mock_messages)

    try:
        summary = await summarize_chat_impl(mock_context, last_n_messages=50)

        assert isinstance(summary, ChatSummary)
        assert summary.message_count == 4
        assert "start" in summary.date_range
        assert "end" in summary.date_range
        assert len(summary.key_topics) > 0

    finally:
        app.adapters.llm.tools.get_recent_messages_impl = original_func


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

    original_func = app.adapters.llm.tools.get_recent_messages_impl
    app.adapters.llm.tools.get_recent_messages_impl = AsyncMock(return_value=mock_messages)

    try:
        tasks = await extract_tasks_impl(mock_context, last_n_messages=100)

        assert len(tasks) >= 1
        assert any("groceries" in task.task for task in tasks)
        assert all(isinstance(task, ExtractedTask) for task in tasks)

    finally:
        app.adapters.llm.tools.get_recent_messages_impl = original_func


@pytest.mark.asyncio
async def test_get_conversation_stats(mock_context):
    """Test conversation statistics."""
    db = mock_context.context["db_session"]

    # Mock count queries
    db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=100)),  # Total messages
        MagicMock(scalar=MagicMock(return_value=60)),  # User messages
        MagicMock(
            one_or_none=MagicMock(
                return_value=MagicMock(
                    first=datetime.utcnow() - timedelta(days=10),
                    last=datetime.utcnow(),
                )
            )
        ),  # Date range
    ]

    stats = await get_conversation_stats_impl(mock_context)

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
    search_results = await search_messages_impl(mock_context, "test")
    assert search_results == []

    recent_results = await get_recent_messages_impl(mock_context, 10)
    assert recent_results == []

    stats = await get_conversation_stats_impl(mock_context)
    assert stats.total_messages == 0
