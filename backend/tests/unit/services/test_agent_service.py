"""Unit tests for agent service."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models import LLMConfig, User
from app.models.llm_config import LLMProvider
from app.schemas.agent import AgentResponse, ToolCall
from app.schemas.message import MessageDirection, MessageResponse
from app.services.agent_service import AgentService


class TestAgentService:
    """Test agent service functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def agent_service(self, mock_db):
        """Create agent service instance."""
        return AgentService(mock_db)

    @pytest.fixture
    def sample_user(self):
        """Create sample user."""
        return User(
            id=1,
            phone_number="+1234567890",
            first_seen=datetime.now(),
            display_name="Test User",
        )

    @pytest.fixture
    def sample_llm_config(self):
        """Create sample LLM configuration."""
        from app.models.llm_config import LLMProvider

        return LLMConfig(
            id=1,
            user_id=1,
            provider=LLMProvider.OPENAI,
            api_key_encrypted="encrypted_key",
            model_settings={
                "model": "gpt-4o",
                "temperature": 0.7,
                "custom_instructions": "Be helpful and concise",
            },
            is_active=True,
        )

    @patch("app.services.agent_service.create_agent")
    @patch("app.services.agent_service.decrypt_api_key")
    async def test_process_message_success(
        self,
        mock_decrypt,
        mock_create_agent,
        agent_service,
        mock_db,
        sample_user,
        sample_llm_config,
    ):
        """Test successful message processing."""
        # Setup mocks
        mock_decrypt.return_value = "decrypted_api_key"
        mock_agent = Mock()
        mock_agent.process_message = AsyncMock(return_value="Hello! How can I help you?")
        mock_agent.update_instructions = Mock()
        mock_create_agent.return_value = mock_agent

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # For _store_incoming_message
            sample_llm_config,  # For _get_user_llm_config
            sample_user,  # For _store_outgoing_message
        ]

        # Mock message service
        agent_service.message_service.store_message = AsyncMock()
        agent_service.message_service.get_recent_messages = AsyncMock(return_value=[])

        # Act
        result = await agent_service.process_message(user_id=1, message_content="Hello world")

        # Assert
        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.content == "Hello! How can I help you?"
        assert result.metadata["provider"] == LLMProvider.OPENAI
        assert result.metadata["model"] == "gpt-4o"

        # Verify agent was created with correct parameters
        mock_create_agent.assert_called_once_with(
            provider=LLMProvider.OPENAI,
            api_key="decrypted_api_key",
            model="gpt-4o",
            temperature=0.7,
        )

        # Verify agent was updated with custom instructions
        mock_agent.update_instructions.assert_called_once_with("Be helpful and concise")

        # Verify messages were stored
        assert agent_service.message_service.store_message.call_count == 2

    async def test_process_message_no_llm_config(self, agent_service, mock_db, sample_user):
        """Test message processing when user has no LLM config."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # For _store_incoming_message
            None,  # For _get_user_llm_config - no config
        ]

        # Mock message service
        agent_service.message_service.store_message = AsyncMock()

        # Act
        result = await agent_service.process_message(user_id=1, message_content="Hello world")

        # Assert
        assert result.success is False
        assert result.error_message == "LLM configuration not found"
        assert "encountered an error" in result.content

    @patch("app.services.agent_service.create_agent")
    @patch("app.services.agent_service.decrypt_api_key")
    async def test_process_message_with_conversation_context(
        self,
        mock_decrypt,
        mock_create_agent,
        agent_service,
        mock_db,
        sample_user,
        sample_llm_config,
    ):
        """Test message processing with existing conversation context."""
        # Setup mocks
        mock_decrypt.return_value = "decrypted_api_key"
        mock_agent = Mock()
        mock_agent.process_message = AsyncMock(return_value="I see you mentioned that earlier.")
        mock_agent.update_instructions = Mock()
        mock_create_agent.return_value = mock_agent

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # For _store_incoming_message
            sample_llm_config,  # For _get_user_llm_config
            sample_user,  # For _store_outgoing_message
        ]

        # Mock recent messages (newest first, as returned by get_recent_messages)
        recent_messages = [
            MessageResponse(
                id=2,
                user_id=1,
                content="Previous response",
                direction=MessageDirection.OUTGOING,
                message_type="text",
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
            MessageResponse(
                id=1,
                user_id=1,
                content="Previous message",
                direction=MessageDirection.INCOMING,
                message_type="text",
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
        ]
        agent_service.message_service.get_recent_messages = AsyncMock(return_value=recent_messages)
        agent_service.message_service.store_message = AsyncMock()

        # Act
        result = await agent_service.process_message(
            user_id=1, message_content="Remember what I said?"
        )

        # Assert
        assert result.success is True

        # Verify conversation history was passed to agent
        call_args = mock_agent.process_message.call_args
        # Messages are reversed (oldest first)
        assert call_args.kwargs["conversation_history"] == [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]

    @patch("app.services.agent_service.create_agent")
    @patch("app.services.agent_service.decrypt_api_key")
    async def test_process_message_agent_error(
        self,
        mock_decrypt,
        mock_create_agent,
        agent_service,
        mock_db,
        sample_user,
        sample_llm_config,
    ):
        """Test message processing when agent fails."""
        # Setup mocks
        mock_decrypt.return_value = "decrypted_api_key"
        mock_agent = Mock()
        mock_agent.process_message = AsyncMock(side_effect=Exception("Agent error"))
        mock_agent.update_instructions = Mock()
        mock_create_agent.return_value = mock_agent

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # For _store_incoming_message
            sample_llm_config,  # For _get_user_llm_config
        ]

        # Mock message service
        agent_service.message_service.store_message = AsyncMock()
        agent_service.message_service.get_recent_messages = AsyncMock(return_value=[])

        # Act
        result = await agent_service.process_message(user_id=1, message_content="Hello world")

        # Assert
        assert result.success is False
        assert "Failed to process message" in result.error_message
        assert "encountered an error" in result.content

    async def test_execute_tool_calls_success(self, agent_service):
        """Test successful tool call execution."""
        # Create mock tools
        mock_tools = Mock()
        mock_tools.execute_tool = AsyncMock(
            side_effect=[
                {"result": "Search results"},
                {"stats": {"total_messages": 100}},
            ]
        )

        # Create tool calls
        tool_calls = [
            ToolCall(id="call_1", function_name="search_messages", arguments={"query": "test"}),
            ToolCall(id="call_2", function_name="get_conversation_stats", arguments={}),
        ]

        # Act
        results = await agent_service.execute_tool_calls(tool_calls, mock_tools)

        # Assert
        assert len(results) == 2
        assert results[0]["role"] == "tool"
        assert results[0]["tool_call_id"] == "call_1"
        assert '{"result": "Search results"}' in results[0]["content"]
        assert results[1]["tool_call_id"] == "call_2"
        assert "total_messages" in results[1]["content"]

    async def test_execute_tool_calls_with_error(self, agent_service):
        """Test tool call execution with errors."""
        # Create mock tools
        mock_tools = Mock()
        mock_tools.execute_tool = AsyncMock(side_effect=Exception("Tool error"))

        # Create tool call
        tool_calls = [
            ToolCall(id="call_1", function_name="search_messages", arguments={"query": "test"})
        ]

        # Act
        results = await agent_service.execute_tool_calls(tool_calls, mock_tools)

        # Assert
        assert len(results) == 1
        assert results[0]["role"] == "tool"
        assert results[0]["tool_call_id"] == "call_1"
        assert "error" in results[0]["content"]
        assert "Tool error" in results[0]["content"]

    async def test_build_conversation_context(self, agent_service, mock_db):
        """Test building conversation context from messages."""
        # Mock recent messages (newest first, as returned by get_recent_messages)
        recent_messages = [
            MessageResponse(
                id=3,
                user_id=1,
                content="System message",
                direction=MessageDirection.SYSTEM,
                message_type="text",
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
            MessageResponse(
                id=2,
                user_id=1,
                content="Hi there!",
                direction=MessageDirection.OUTGOING,
                message_type="text",
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
            MessageResponse(
                id=1,
                user_id=1,
                content="Hello",
                direction=MessageDirection.INCOMING,
                message_type="text",
                whatsapp_message_id=None,
                metadata=None,
                created_at=datetime.now(),
            ),
        ]
        agent_service.message_service.get_recent_messages = AsyncMock(return_value=recent_messages)

        # Act
        context = await agent_service._build_conversation_context(user_id=1)

        # Assert
        assert len(context) == 2  # System messages excluded
        assert context[0] == {"role": "user", "content": "Hello"}
        assert context[1] == {"role": "assistant", "content": "Hi there!"}

    def test_create_error_response(self, agent_service):
        """Test error response creation."""
        response = agent_service._create_error_response("Test error")

        assert isinstance(response, AgentResponse)
        assert response.success is False
        assert response.error_message == "Test error"
        assert "encountered an error" in response.content
