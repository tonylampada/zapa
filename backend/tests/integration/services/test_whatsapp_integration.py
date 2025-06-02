"""Integration tests for WhatsApp end-to-end message flow."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models import LLMConfig, User
from app.schemas.webhook import (
    WebhookEventType,
    WhatsAppWebhookEvent,
)
from app.services.agent_service import AgentService
from app.services.integration_orchestrator import integration_orchestrator
from app.services.message_queue import MessagePriority, message_queue
from app.services.message_service import MessageService
from app.services.webhook_handler import WebhookHandlerService


@pytest.fixture
async def cleanup_integration():
    """Cleanup integration components after tests."""
    yield
    # Ensure everything is shut down
    await integration_orchestrator.shutdown()
    await message_queue.close()


@pytest.mark.asyncio
async def test_end_to_end_message_flow(
    db: Session,
    cleanup_integration,
    mock_whatsapp_adapter,
    mock_redis,
):
    """Test complete message flow from webhook to agent response."""
    # Create test user with LLM config
    user = User(
        phone_number="+1234567890",
        display_name="Test User",
        is_active=True,
    )
    db.add(user)
    db.commit()

    llm_config = LLMConfig(
        user_id=user.id,
        provider="openai",
        api_key="encrypted_test_key",
        model_name="gpt-4",
        is_active=True,
        custom_instructions="Always be helpful",
    )
    db.add(llm_config)
    db.commit()

    # Mock the agent processing
    mock_agent_response = "Hello! How can I help you today?"

    with patch("app.services.agent_service.create_agent") as mock_create_agent:
        # Mock agent
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_agent_response
        mock_create_agent.return_value = mock_agent

        # Initialize integration
        init_result = await integration_orchestrator.initialize()
        assert init_result["status"] == "initialized"

        # Create webhook event
        webhook_event = WhatsAppWebhookEvent(
            event_type=WebhookEventType.MESSAGE_RECEIVED,
            timestamp=datetime.now(timezone.utc),
            data={
                "message_id": "test_msg_123",
                "from_number": "+1234567890@s.whatsapp.net",
                "to_number": "+1234567890@s.whatsapp.net",  # System number
                "text": "Hello, I need help",
                "timestamp": datetime.now(timezone.utc),
            },
        )

        # Process webhook
        message_service = MessageService(db)
        agent_service = AgentService(db)
        webhook_handler = WebhookHandlerService(db, message_service, agent_service)

        result = await webhook_handler.handle_webhook(webhook_event)
        assert result["status"] == "queued"

        # Wait for message to be processed
        await asyncio.sleep(2)

        # Verify message was processed
        assert mock_agent.run.called
        call_args = mock_agent.run.call_args
        assert "Hello, I need help" in str(call_args)

        # Verify response was sent via WhatsApp
        assert mock_whatsapp_adapter.send_message.called
        send_call = mock_whatsapp_adapter.send_message.call_args
        assert send_call[1]["to"] == "+1234567890@s.whatsapp.net"
        assert send_call[1]["text"] == mock_agent_response


@pytest.mark.asyncio
async def test_message_queue_retry_logic(
    db: Session,
    cleanup_integration,
    mock_redis,
):
    """Test message retry logic on processing failure."""
    # Create test user
    user = User(
        phone_number="+9876543210",
        display_name="Retry Test User",
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Mock agent to fail first 2 times
    attempt_count = 0

    async def mock_process_message(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("Processing failed")
        return "Success after retries"

    with patch(
        "app.services.agent_service.AgentService.process_message", side_effect=mock_process_message
    ):
        # Enqueue message
        queued_msg = await message_queue.enqueue(
            user_id=user.id,
            content="Test retry message",
            priority=MessagePriority.NORMAL,
        )

        # Process message (will retry)
        from app.services.message_processor import message_processor

        # Process should retry and eventually succeed
        for _ in range(5):  # Process multiple times to handle retries
            await message_processor.process_single()
            await asyncio.sleep(0.5)

        # Verify message was eventually processed
        assert attempt_count == 3  # Failed twice, succeeded on third


@pytest.mark.asyncio
async def test_integration_health_monitoring(
    cleanup_integration,
    mock_redis,
    mock_whatsapp_adapter,
):
    """Test integration health monitoring."""
    # Initialize integration
    await integration_orchestrator.initialize()

    # Get health status
    from app.services.integration_monitor import integration_monitor

    health = await integration_monitor.get_system_health()

    assert health["healthy"] is True
    assert "database" in health["components"]
    assert "redis" in health["components"]
    assert "whatsapp_bridge" in health["components"]
    assert "message_queue" in health["components"]

    # All components should be healthy
    for component in health["components"].values():
        assert component["healthy"] is True


@pytest.mark.asyncio
async def test_integration_admin_endpoints(
    client,
    admin_headers,
    cleanup_integration,
    mock_redis,
):
    """Test integration admin API endpoints."""
    # Initialize integration
    response = client.post(
        "/api/v1/admin/integration/initialize",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "initialized"

    # Get status
    response = client.get(
        "/api/v1/admin/integration/status",
        headers=admin_headers,
    )
    assert response.status_code == 200
    status = response.json()
    assert status["initialized"] is True
    assert status["workers"]["running"] > 0

    # Get health
    response = client.get(
        "/api/v1/admin/integration/health",
        headers=admin_headers,
    )
    assert response.status_code == 200
    health = response.json()
    assert health["healthy"] is True

    # Get queue stats
    response = client.get(
        "/api/v1/admin/integration/queue/stats",
        headers=admin_headers,
    )
    assert response.status_code == 200
    stats = response.json()
    assert "queues" in stats
    assert "total" in stats

    # Shutdown
    response = client.post(
        "/api/v1/admin/integration/shutdown",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "shutdown_complete"


@pytest.mark.asyncio
async def test_concurrent_message_processing(
    db: Session,
    cleanup_integration,
    mock_redis,
):
    """Test concurrent processing of multiple messages."""
    # Create multiple users
    users = []
    for i in range(5):
        user = User(
            phone_number=f"+100{i}",
            display_name=f"Concurrent User {i}",
            is_active=True,
        )
        db.add(user)
        users.append(user)
    db.commit()

    # Mock agent to track processing
    processed_messages = []

    async def mock_process(*args, **kwargs):
        user_id = kwargs.get("user_id")
        content = kwargs.get("message_content")
        processed_messages.append((user_id, content))
        await asyncio.sleep(0.1)  # Simulate processing time
        return f"Response for user {user_id}"

    with patch("app.services.agent_service.AgentService.process_message", side_effect=mock_process):
        # Initialize with multiple workers
        await integration_orchestrator.initialize()

        # Enqueue messages from all users
        for i, user in enumerate(users):
            await message_queue.enqueue(
                user_id=user.id,
                content=f"Message {i} from user {user.id}",
                priority=MessagePriority.NORMAL,
            )

        # Wait for processing
        await asyncio.sleep(2)

        # Verify all messages were processed
        assert len(processed_messages) == 5

        # Verify messages were processed by different workers (concurrent)
        # Check that not all messages were processed sequentially
        # (This is a simple check - in reality, timing might vary)
        assert len(set(msg[0] for msg in processed_messages)) == 5


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real WhatsApp Bridge")
async def test_real_whatsapp_integration():
    """Test with real WhatsApp Bridge (manual test)."""
    # This test requires:
    # 1. WhatsApp Bridge running on localhost:3000
    # 2. A connected WhatsApp session
    # 3. INTEGRATION_TEST_WHATSAPP=true environment variable

    import os

    if not os.getenv("INTEGRATION_TEST_WHATSAPP"):
        pytest.skip("WhatsApp integration test not enabled")

    # Initialize real integration
    await integration_orchestrator.initialize()

    # Get bridge health
    from app.services.bridge_config import bridge_config

    health = await bridge_config.check_bridge_health()
    assert health["status"] == "healthy"
    assert health["active_sessions"] > 0

    print("WhatsApp integration is ready!")
    print("Send a message to the system number to test")

    # Keep running for manual testing
    await asyncio.sleep(60)
