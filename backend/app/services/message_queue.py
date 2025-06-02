"""Message queue service for reliable message processing using Redis."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

import redis.asyncio as redis
from pydantic import BaseModel, Field

from app.config.redis import redis_settings

logger = logging.getLogger(__name__)


class MessagePriority(str, Enum):
    """Message priority levels."""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class QueuedMessage(BaseModel):
    """Model for a message in the queue."""

    id: str = Field(description="Unique message ID")
    user_id: int = Field(description="User ID for the message")
    content: str = Field(description="Message content")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=redis_settings.message_queue_max_retries)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageQueueService:
    """Service for managing message queues with Redis."""

    def __init__(self) -> None:
        """Initialize the message queue service."""
        self._redis: Optional[redis.Redis] = None
        self._is_connected = False
        self._processing_lock: Optional[asyncio.Lock] = None

    @asynccontextmanager
    async def _get_redis(self) -> AsyncGenerator[redis.Redis, None]:
        """Get Redis connection with context manager."""
        if not self._redis or not self._is_connected:
            self._redis = await redis.from_url(
                redis_settings.redis_url,
                max_connections=redis_settings.redis_max_connections,
                decode_responses=redis_settings.redis_decode_responses,
                socket_timeout=redis_settings.redis_socket_timeout,
                retry_on_timeout=redis_settings.redis_retry_on_timeout,
            )
            self._is_connected = True
            self._processing_lock = asyncio.Lock()

        try:
            yield self._redis
        except Exception as e:
            logger.error(f"Redis error: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._is_connected = False
            self._redis = None

    def _get_queue_key(self, priority: MessagePriority) -> str:
        """Get Redis key for a priority queue."""
        return f"{redis_settings.message_queue_prefix}{priority.value}"

    def _get_processing_key(self) -> str:
        """Get Redis key for messages being processed."""
        return f"{redis_settings.message_queue_prefix}processing"

    def _get_failed_key(self) -> str:
        """Get Redis key for failed messages."""
        return f"{redis_settings.message_queue_prefix}failed"

    async def enqueue(
        self,
        user_id: int,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueuedMessage:
        """Add a message to the queue."""
        message = QueuedMessage(
            id=f"{user_id}:{int(time.time() * 1000000)}",
            user_id=user_id,
            content=content,
            priority=priority,
            metadata=metadata or {},
        )

        async with self._get_redis() as r:
            # Add to appropriate priority queue
            queue_key = self._get_queue_key(priority)
            await r.lpush(queue_key, message.model_dump_json())
            
            # Set expiration on the message
            await r.expire(queue_key, redis_settings.message_queue_ttl)

        logger.info(f"Enqueued message {message.id} with priority {priority}")
        return message

    async def dequeue(
        self, priorities: Optional[List[MessagePriority]] = None
    ) -> Optional[QueuedMessage]:
        """Get the next message from the queue."""
        if priorities is None:
            priorities = [MessagePriority.HIGH, MessagePriority.NORMAL, MessagePriority.LOW]

        async with self._get_redis() as r:
            # Try each priority queue in order
            for priority in priorities:
                queue_key = self._get_queue_key(priority)
                processing_key = self._get_processing_key()

                # Move message from queue to processing set atomically
                message_data = await r.rpoplpush(queue_key, processing_key)
                if message_data:
                    message = QueuedMessage.model_validate_json(message_data)
                    message.last_attempt_at = datetime.now(timezone.utc)
                    
                    # Update the message in the processing set
                    await r.lrem(processing_key, 1, message_data)
                    await r.lpush(processing_key, message.model_dump_json())
                    
                    logger.info(f"Dequeued message {message.id} from {priority} queue")
                    return message

        return None

    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge successful processing of a message."""
        async with self._get_redis() as r:
            processing_key = self._get_processing_key()
            
            # Find and remove the message from processing
            messages = await r.lrange(processing_key, 0, -1)
            for msg_data in messages:
                msg = QueuedMessage.model_validate_json(msg_data)
                if msg.id == message_id:
                    await r.lrem(processing_key, 1, msg_data)
                    logger.info(f"Acknowledged message {message_id}")
                    return True

        logger.warning(f"Message {message_id} not found in processing queue")
        return False

    async def retry(self, message: QueuedMessage, error: str) -> bool:
        """Retry a failed message."""
        message.retry_count += 1
        message.error = error
        message.last_attempt_at = datetime.now(timezone.utc)

        async with self._get_redis() as r:
            processing_key = self._get_processing_key()
            
            # Remove from processing queue
            messages = await r.lrange(processing_key, 0, -1)
            for msg_data in messages:
                msg = QueuedMessage.model_validate_json(msg_data)
                if msg.id == message.id:
                    await r.lrem(processing_key, 1, msg_data)
                    break

            if message.retry_count >= message.max_retries:
                # Move to failed queue
                failed_key = self._get_failed_key()
                await r.lpush(failed_key, message.model_dump_json())
                logger.error(f"Message {message.id} exceeded max retries, moved to failed queue")
                return False
            else:
                # Calculate exponential backoff delay
                delay = redis_settings.message_queue_retry_delay * (2 ** (message.retry_count - 1))
                
                # Re-queue with lower priority after delay
                await asyncio.sleep(delay)
                queue_key = self._get_queue_key(MessagePriority.LOW)
                await r.lpush(queue_key, message.model_dump_json())
                logger.info(f"Retrying message {message.id} (attempt {message.retry_count})")
                return True

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the message queues."""
        async with self._get_redis() as r:
            stats = {
                "queues": {},
                "processing": 0,
                "failed": 0,
                "total": 0,
            }

            # Get counts for each priority queue
            for priority in MessagePriority:
                queue_key = self._get_queue_key(priority)
                count = await r.llen(queue_key)
                stats["queues"][priority.value] = count
                stats["total"] += count

            # Get processing and failed counts
            stats["processing"] = await r.llen(self._get_processing_key())
            stats["failed"] = await r.llen(self._get_failed_key())
            stats["total"] += stats["processing"] + stats["failed"]

            return stats

    async def clear_failed(self) -> int:
        """Clear all failed messages."""
        async with self._get_redis() as r:
            failed_key = self._get_failed_key()
            count = await r.llen(failed_key)
            await r.delete(failed_key)
            logger.info(f"Cleared {count} failed messages")
            return count

    async def requeue_failed(self) -> int:
        """Requeue all failed messages for retry."""
        async with self._get_redis() as r:
            failed_key = self._get_failed_key()
            messages = await r.lrange(failed_key, 0, -1)
            count = 0

            for msg_data in messages:
                msg = QueuedMessage.model_validate_json(msg_data)
                msg.retry_count = 0  # Reset retry count
                msg.error = None
                
                # Add back to normal priority queue
                queue_key = self._get_queue_key(MessagePriority.NORMAL)
                await r.lpush(queue_key, msg.model_dump_json())
                count += 1

            # Clear failed queue
            await r.delete(failed_key)
            logger.info(f"Requeued {count} failed messages")
            return count


# Global instance
message_queue = MessageQueueService()