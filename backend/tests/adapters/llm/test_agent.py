"""Tests for Zapa Agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
        mock_runner.run = AsyncMock(return_value=mock_result)

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
        {
            "role": "assistant",
            "content": "I can't check weather, but I can help with your messages.",
        },
    ]

    with patch("app.adapters.llm.agent.Runner") as mock_runner:
        mock_result = MagicMock()
        mock_result.final_output = "Based on our conversation..."
        mock_runner.run = AsyncMock(return_value=mock_result)

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
        mock_runner.run = AsyncMock(side_effect=Exception("API Error"))

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
    # Note: Agent model is immutable in the SDK


def test_create_agent_openai():
    """Test creating OpenAI agent."""
    agent = create_agent(
        provider="openai",
        api_key="test-key",
        model="gpt-4",
    )

    assert isinstance(agent, ZapaAgent)
    assert agent.model == "gpt-4"
    assert agent.model_provider is not None


def test_create_agent_anthropic():
    """Test creating Anthropic agent."""
    agent = create_agent(
        provider="anthropic",
        api_key="test-key",
    )

    assert isinstance(agent, ZapaAgent)
    assert agent.model == "claude-3-opus-20240229"
    assert agent.model_provider is not None


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
    assert agent.model_provider is not None
