"""Unit tests for the message queue service."""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.message_queue import (
    MessagePriority,
    MessageQueueService,
    QueuedMessage,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.lpush = AsyncMock()
    redis_mock.rpoplpush = AsyncMock()
    redis_mock.lrange = AsyncMock()
    redis_mock.lrem = AsyncMock()
    redis_mock.llen = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.expire = AsyncMock()
    redis_mock.close = AsyncMock()
    return redis_mock


@pytest.fixture
def message_queue_service(mock_redis):
    """Create message queue service with mocked Redis."""
    service = MessageQueueService()

    # Create async function that returns the mock
    async def mock_from_url(*args, **kwargs):
        return mock_redis

    # Mock the Redis connection
    with patch("app.services.message_queue.redis.from_url", side_effect=mock_from_url):
        yield service


@pytest.mark.asyncio
async def test_enqueue_message(message_queue_service, mock_redis):
    """Test enqueueing a message."""
    # Enqueue a message
    message = await message_queue_service.enqueue(
        user_id=1,
        content="Test message",
        priority=MessagePriority.HIGH,
        metadata={"source": "test"},
    )

    # Verify message properties
    assert message.user_id == 1
    assert message.content == "Test message"
    assert message.priority == MessagePriority.HIGH
    assert message.metadata == {"source": "test"}
    assert message.retry_count == 0

    # Verify Redis calls
    mock_redis.lpush.assert_called_once()
    args = mock_redis.lpush.call_args[0]
    assert args[0] == "zapa:queue:high"

    # Verify message was serialized correctly
    stored_msg = QueuedMessage.model_validate_json(args[1])
    assert stored_msg.content == "Test message"

    mock_redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_dequeue_message(message_queue_service, mock_redis):
    """Test dequeuing a message."""
    # Mock a message in the queue
    test_message = QueuedMessage(
        id="1:123456",
        user_id=1,
        content="Test message",
        priority=MessagePriority.NORMAL,
    )
    mock_redis.rpoplpush.return_value = test_message.model_dump_json()

    # Dequeue the message
    message = await message_queue_service.dequeue()

    # Verify the message
    assert message is not None
    assert message.id == "1:123456"
    assert message.content == "Test message"
    assert message.last_attempt_at is not None

    # Verify Redis calls
    mock_redis.rpoplpush.assert_called()
    mock_redis.lrem.assert_called_once()
    mock_redis.lpush.assert_called()


@pytest.mark.asyncio
async def test_dequeue_respects_priority(message_queue_service, mock_redis):
    """Test that dequeue respects priority order."""
    # Create a low priority message
    low_priority_msg = QueuedMessage(
        id="1:789",
        user_id=1,
        content="Low priority message",
        priority=MessagePriority.LOW,
    )

    # Mock no messages in high and normal queues, message in low queue
    mock_redis.rpoplpush.side_effect = [None, None, low_priority_msg.model_dump_json()]

    # Dequeue should check all priorities
    message = await message_queue_service.dequeue()

    # Verify all priority queues were checked in order
    assert mock_redis.rpoplpush.call_count == 3
    calls = mock_redis.rpoplpush.call_args_list
    assert calls[0][0][0] == "zapa:queue:high"
    assert calls[1][0][0] == "zapa:queue:normal"
    assert calls[2][0][0] == "zapa:queue:low"

    # Verify we got the low priority message
    assert message is not None
    assert message.content == "Low priority message"


@pytest.mark.asyncio
async def test_acknowledge_message(message_queue_service, mock_redis):
    """Test acknowledging a message."""
    # Mock messages in processing queue
    test_message = QueuedMessage(
        id="1:123456",
        user_id=1,
        content="Test message",
    )
    mock_redis.lrange.return_value = [test_message.model_dump_json()]

    # Acknowledge the message
    result = await message_queue_service.acknowledge("1:123456")

    # Verify success
    assert result is True
    mock_redis.lrem.assert_called_once()


@pytest.mark.asyncio
async def test_retry_message(message_queue_service, mock_redis):
    """Test retrying a failed message."""
    # Create a message with one retry
    test_message = QueuedMessage(
        id="1:123456",
        user_id=1,
        content="Test message",
        retry_count=1,
    )

    # Mock finding the message in processing
    mock_redis.lrange.return_value = [test_message.model_dump_json()]

    # Retry the message
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await message_queue_service.retry(test_message, "Test error")

    # Verify retry was successful
    assert result is True
    assert test_message.retry_count == 2
    assert test_message.error == "Test error"

    # Verify message was re-queued
    mock_redis.lrem.assert_called_once()
    mock_redis.lpush.assert_called()

    # Check it was added to low priority queue
    lpush_calls = mock_redis.lpush.call_args_list
    assert any("zapa:queue:low" in str(call) for call in lpush_calls)


@pytest.mark.asyncio
async def test_retry_exceeds_max_retries(message_queue_service, mock_redis):
    """Test message moved to failed queue after max retries."""
    # Create a message at max retries
    test_message = QueuedMessage(
        id="1:123456",
        user_id=1,
        content="Test message",
        retry_count=2,  # Will be 3 after increment
        max_retries=3,
    )

    # Mock finding the message
    mock_redis.lrange.return_value = [test_message.model_dump_json()]

    # Retry should fail
    result = await message_queue_service.retry(test_message, "Final error")

    # Verify failure
    assert result is False
    assert test_message.retry_count == 3

    # Verify message was moved to failed queue
    lpush_calls = mock_redis.lpush.call_args_list
    assert any("zapa:queue:failed" in str(call) for call in lpush_calls)


@pytest.mark.asyncio
async def test_get_queue_stats(message_queue_service, mock_redis):
    """Test getting queue statistics."""
    # Mock queue lengths
    mock_redis.llen.side_effect = [5, 10, 2, 3, 1]  # high, normal, low, processing, failed

    # Get stats
    stats = await message_queue_service.get_queue_stats()

    # Verify stats
    assert stats["queues"]["high"] == 5
    assert stats["queues"]["normal"] == 10
    assert stats["queues"]["low"] == 2
    assert stats["processing"] == 3
    assert stats["failed"] == 1
    assert stats["total"] == 21


@pytest.mark.asyncio
async def test_clear_failed(message_queue_service, mock_redis):
    """Test clearing failed messages."""
    # Mock failed queue length
    mock_redis.llen.return_value = 5

    # Clear failed
    count = await message_queue_service.clear_failed()

    # Verify
    assert count == 5
    mock_redis.delete.assert_called_once_with("zapa:queue:failed")


@pytest.mark.asyncio
async def test_requeue_failed(message_queue_service, mock_redis):
    """Test requeuing failed messages."""
    # Mock failed messages
    failed_messages = [
        QueuedMessage(
            id=f"1:{i}",
            user_id=1,
            content=f"Failed message {i}",
            retry_count=3,
            error="Previous error",
        ).model_dump_json()
        for i in range(3)
    ]
    mock_redis.lrange.return_value = failed_messages

    # Requeue failed
    count = await message_queue_service.requeue_failed()

    # Verify
    assert count == 3
    assert mock_redis.lpush.call_count == 3
    mock_redis.delete.assert_called_once_with("zapa:queue:failed")
