"""Integration tests for agent service."""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.encryption import encrypt_api_key
from app.models import Base, LLMConfig, Message, Session, User
from app.models.llm_config import LLMProvider
from app.models.session import SessionStatus, SessionType
from app.schemas.message import MessageCreate
from app.services.agent_service import AgentService
from app.services.message_service import MessageService

# Skip all tests if integration testing is not enabled
pytestmark = pytest.mark.skipif(
    not any(
        [
            os.getenv("INTEGRATION_TEST_OPENAI") == "true",
            os.getenv("INTEGRATION_TEST_ANTHROPIC") == "true",
            os.getenv("INTEGRATION_TEST_GOOGLE") == "true",
        ]
    ),
    reason="Integration tests require INTEGRATION_TEST_* environment variable",
)


class TestAgentIntegration:
    """Integration tests for agent service with real database and mocked LLM."""

    @pytest.fixture
    def db_engine(self):
        """Create test database engine."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session for tests."""
        session_local = sessionmaker(bind=db_engine)
        session = session_local()
        yield session
        session.close()

    @pytest.fixture
    def test_user(self, db_session):
        """Create test user."""
        user = User(
            phone_number="+1234567890",
            is_active=True,
            preferences={"language": "en"},
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def test_session(self, db_session, test_user):
        """Create test session."""
        session = Session(
            user_id=test_user.id,
            session_type=SessionType.CHAT,
            status=SessionStatus.ACTIVE,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        return session

    @pytest.fixture
    def test_llm_config(self, db_session, test_user):
        """Create test LLM configuration."""
        # Use real API key if available, otherwise use dummy
        api_key = os.getenv("OPENAI_API_KEY", "test-api-key")
        config = LLMConfig(
            user_id=test_user.id,
            provider=LLMProvider.OPENAI,
            api_key_encrypted=encrypt_api_key(api_key),
            model_name="gpt-4o",
            model_settings={"temperature": 0.7, "max_tokens": 1000},
            custom_instructions="You are a helpful assistant. Be concise.",
            is_active=True,
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)
        return config

    @pytest.fixture
    def agent_service(self, db_session):
        """Create agent service with real database."""
        return AgentService(db_session)

    @pytest.fixture
    def message_service(self, db_session):
        """Create message service with real database."""
        return MessageService(db_session)

    @pytest.fixture
    async def seed_messages(self, db_session, test_user, test_session, message_service):
        """Seed database with test messages."""
        messages_data = [
            ("Hello, I need help", "incoming", datetime.now() - timedelta(hours=2)),
            ("Hi! How can I assist you?", "outgoing", datetime.now() - timedelta(hours=2)),
            ("Can you remind me about my tasks?", "incoming", datetime.now() - timedelta(hours=1)),
            ("Sure! Let me help you with that.", "outgoing", datetime.now() - timedelta(hours=1)),
            ("What's the weather like?", "incoming", datetime.now() - timedelta(minutes=30)),
            (
                "I don't have weather information.",
                "outgoing",
                datetime.now() - timedelta(minutes=30),
            ),
        ]

        for content, direction, _ in messages_data:
            if direction == "incoming":
                sender = test_user.phone_number
                recipient = "system@zapa.ai"
            else:
                sender = "system@zapa.ai"
                recipient = test_user.phone_number

            message_data = MessageCreate(
                sender_jid=sender,
                recipient_jid=recipient,
                content=content,
                message_type="text",
            )
            await message_service.store_message(test_user.id, message_data)

    @pytest.mark.skipif(
        os.getenv("INTEGRATION_TEST_OPENAI") != "true",
        reason="OpenAI integration test not enabled",
    )
    @patch("app.adapters.llm.agent.Runner.run")
    async def test_agent_process_message_with_context(
        self, mock_runner, agent_service, test_user, test_llm_config, seed_messages
    ):
        """Test agent processing with conversation context."""
        # Mock the agent response
        mock_result = AsyncMock()
        mock_result.final_output = (
            "Based on your conversation history, you asked about tasks and weather."
        )
        mock_runner.return_value = mock_result

        # Process message
        result = await agent_service.process_message(
            user_id=test_user.id, message_content="What have we talked about?"
        )

        # Verify response
        assert result.success is True
        assert "tasks and weather" in result.content
        assert result.metadata["provider"] == "openai"
        assert result.metadata["model"] == "gpt-4o"

        # Verify conversation context was built
        call_args = mock_runner.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) > 0
        assert any("tasks" in msg["content"] for msg in messages)

    @patch("app.adapters.llm.agent.Runner.run")
    async def test_agent_with_tool_execution(
        self, mock_runner, agent_service, test_user, test_llm_config, seed_messages
    ):
        """Test agent executing tools to search messages."""
        # Mock agent making a tool call
        mock_result = AsyncMock()
        mock_result.final_output = "I found 3 messages about tasks in your history."
        mock_runner.return_value = mock_result

        # Process message
        result = await agent_service.process_message(
            user_id=test_user.id, message_content="Search for messages about tasks"
        )

        # Verify response
        assert result.success is True
        assert "messages about tasks" in result.content

    async def test_agent_without_llm_config(self, agent_service, test_user):
        """Test agent behavior when user has no LLM configuration."""
        result = await agent_service.process_message(user_id=test_user.id, message_content="Hello")

        assert result.success is False
        assert result.error_message == "LLM configuration not found"

    @patch("app.adapters.llm.agent.Runner.run")
    async def test_agent_error_handling(
        self, mock_runner, agent_service, test_user, test_llm_config
    ):
        """Test agent error handling when LLM fails."""
        # Mock agent failure
        mock_runner.side_effect = Exception("LLM API error")

        # Process message
        result = await agent_service.process_message(user_id=test_user.id, message_content="Hello")

        # Verify error response
        assert result.success is False
        assert "Failed to process message" in result.error_message

    @pytest.mark.skipif(
        os.getenv("INTEGRATION_TEST_OPENAI") != "true",
        reason="OpenAI integration test not enabled",
    )
    async def test_real_openai_agent(
        self, agent_service, test_user, test_llm_config, seed_messages
    ):
        """Test with real OpenAI API (requires valid API key)."""
        if os.getenv("OPENAI_API_KEY") == "test-api-key":
            pytest.skip("Real OpenAI API key not provided")

        # Process a real message
        result = await agent_service.process_message(
            user_id=test_user.id,
            message_content="Based on my message history, what have I asked about?",
        )

        # Verify we got a real response
        assert result.success is True
        assert len(result.content) > 0
        # The response should mention tasks or weather based on seed messages
        assert any(word in result.content.lower() for word in ["task", "weather", "help"])

    async def test_message_storage_integration(
        self, agent_service, test_user, test_llm_config, db_session
    ):
        """Test that messages are properly stored during agent processing."""
        with patch("app.adapters.llm.agent.Runner.run") as mock_runner:
            mock_result = AsyncMock()
            mock_result.final_output = "Test response"
            mock_runner.return_value = mock_result

            # Process message
            await agent_service.process_message(
                user_id=test_user.id, message_content="Test message"
            )

            # Verify messages were stored
            messages = db_session.query(Message).filter(Message.user_id == test_user.id).all()
            assert len(messages) == 2  # Input and response

            # Check input message
            input_msg = next(m for m in messages if m.sender_jid == test_user.phone_number)
            assert input_msg.content == "Test message"

            # Check response message
            response_msg = next(m for m in messages if m.sender_jid == "system@zapa.ai")
            assert response_msg.content == "Test response"
