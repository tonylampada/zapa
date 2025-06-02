"""Unit tests for LLM tools."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.llm_tools import LLMTools
from app.schemas.message import ConversationStats, MessageDirection, MessageResponse, MessageType


class TestLLMTools:
    """Test LLM tools functionality."""

    @pytest.fixture
    def mock_message_service(self):
        """Create mock message service."""
        return AsyncMock()

    @pytest.fixture
    def llm_tools(self, mock_message_service):
        """Create LLM tools instance."""
        return LLMTools(user_id=1, message_service=mock_message_service)

    def test_get_tool_definitions(self, llm_tools):
        """Test tool definitions are correctly formatted."""
        definitions = llm_tools.get_tool_definitions()

        assert len(definitions) == 4
        assert all(d["type"] == "function" for d in definitions)

        # Check tool names
        tool_names = [d["function"]["name"] for d in definitions]
        assert "search_messages" in tool_names
        assert "get_recent_messages" in tool_names
        assert "get_messages_by_date_range" in tool_names
        assert "get_conversation_stats" in tool_names

        # Check search_messages parameters
        search_tool = next(d for d in definitions if d["function"]["name"] == "search_messages")
        assert "query" in search_tool["function"]["parameters"]["required"]
        assert "limit" in search_tool["function"]["parameters"]["properties"]

    async def test_execute_tool_valid(self, llm_tools, mock_message_service):
        """Test executing a valid tool."""
        # Mock search results at the message service level
        mock_messages = [
            MessageResponse(
                id=1,
                user_id=1,
                content="Test message",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            )
        ]
        mock_message_service.search_messages.return_value = mock_messages

        result = await llm_tools.execute_tool("search_messages", {"query": "test", "limit": 5})

        assert len(result) == 1
        assert result[0]["content"] == "Test message"
        assert result[0]["direction"] == MessageDirection.INCOMING
        mock_message_service.search_messages.assert_called_once_with(1, "test", 5)

    async def test_execute_tool_invalid(self, llm_tools):
        """Test executing an invalid tool."""
        with pytest.raises(ValueError, match="Unknown tool: invalid_tool"):
            await llm_tools.execute_tool("invalid_tool", {})

    async def test_search_messages(self, llm_tools, mock_message_service):
        """Test search messages tool."""
        # Mock message service response
        mock_messages = [
            MessageResponse(
                id=1,
                user_id=1,
                content="Hello world",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
            MessageResponse(
                id=2,
                user_id=1,
                content="How are you?",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
        ]
        mock_message_service.search_messages.return_value = mock_messages

        result = await llm_tools.search_messages("hello", limit=10)

        assert len(result) == 2
        assert result[0]["content"] == "Hello world"
        assert result[0]["direction"] == MessageDirection.INCOMING
        assert result[1]["content"] == "How are you?"
        assert result[1]["direction"] == MessageDirection.OUTGOING

        mock_message_service.search_messages.assert_called_once_with(1, "hello", 10)

    async def test_get_recent_messages(self, llm_tools, mock_message_service):
        """Test get recent messages tool."""
        # Mock message service response
        mock_messages = [
            MessageResponse(
                id=1,
                user_id=1,
                content="Recent message 1",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now() - timedelta(minutes=5),
            ),
            MessageResponse(
                id=2,
                user_id=1,
                content="Recent message 2",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
        ]
        mock_message_service.get_recent_messages.return_value = mock_messages

        result = await llm_tools.get_recent_messages(count=5)

        assert len(result) == 2
        assert result[0]["content"] == "Recent message 1"
        assert result[1]["content"] == "Recent message 2"

        mock_message_service.get_recent_messages.assert_called_once_with(1, 5)

    async def test_get_messages_by_date_range(self, llm_tools, mock_message_service):
        """Test get messages by date range tool."""
        # Mock message service response
        test_date = datetime(2024, 1, 15, 10, 0, 0)
        mock_messages = [
            MessageResponse(
                id=1,
                user_id=1,
                content="Message in range",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
                whatsapp_message_id=None,
                metadata=None,
                created_at=test_date,
            )
        ]
        mock_message_service.get_messages_by_date_range.return_value = mock_messages

        result = await llm_tools.get_messages_by_date_range(
            start_date="2024-01-01", end_date="2024-01-31"
        )

        assert len(result) == 1
        assert result[0]["content"] == "Message in range"
        assert result[0]["timestamp"] == test_date.isoformat()

        # Check date parsing
        args = mock_message_service.get_messages_by_date_range.call_args[0]
        assert args[0] == 1  # user_id
        assert args[1] == datetime(2024, 1, 1)  # start_date
        assert args[2] == datetime(2024, 1, 31)  # end_date

    async def test_get_conversation_stats(self, llm_tools, mock_message_service):
        """Test get conversation stats tool."""
        # Mock stats
        mock_stats = ConversationStats(
            total_messages=100,
            messages_sent=40,
            messages_received=60,
            first_message_date=datetime(2024, 1, 1),
            last_message_date=datetime(2024, 1, 31),
            average_messages_per_day=3.33,
        )
        mock_message_service.get_conversation_stats.return_value = mock_stats

        result = await llm_tools.get_conversation_stats()

        assert result["total_messages"] == 100
        assert result["messages_sent"] == 40
        assert result["messages_received"] == 60
        assert result["first_message_date"] == "2024-01-01T00:00:00"
        assert result["last_message_date"] == "2024-01-31T00:00:00"
        assert result["average_messages_per_day"] == 3.33

        mock_message_service.get_conversation_stats.assert_called_once_with(1)

    async def test_get_conversation_stats_no_messages(self, llm_tools, mock_message_service):
        """Test conversation stats with no messages."""
        # Mock empty stats
        mock_stats = ConversationStats(
            total_messages=0,
            messages_sent=0,
            messages_received=0,
            first_message_date=None,
            last_message_date=None,
            average_messages_per_day=0.0,
        )
        mock_message_service.get_conversation_stats.return_value = mock_stats

        result = await llm_tools.get_conversation_stats()

        assert result["total_messages"] == 0
        assert result["first_message_date"] is None
        assert result["last_message_date"] is None
