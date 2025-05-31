"""Integration tests for Zapa Agent."""
import os

import pytest

from app.adapters.llm.agent import create_agent
from app.models import Message, User
from backend.tests.fixtures import DatabaseTestManager

# Skip integration tests by default
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_LLM", "false").lower() != "true",
    reason="LLM integration tests disabled. Set INTEGRATION_TEST_LLM=true to run.",
)


@pytest.fixture
async def test_db():
    """Create test database with sample data."""
    async with DatabaseTestManager() as manager:
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
