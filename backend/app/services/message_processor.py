"""Message processor service that consumes from the message queue."""

import asyncio
import logging

from app.core.database import SessionLocal
from app.services.agent_service import AgentService
from app.services.message_queue import QueuedMessage, message_queue

logger = logging.getLogger(__name__)


class MessageProcessorService:
    """Service that processes messages from the queue."""

    def __init__(self) -> None:
        """Initialize the message processor."""
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start processing messages from the queue."""
        if self._running:
            logger.warning("Message processor is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Message processor started")

    async def stop(self) -> None:
        """Stop processing messages."""
        self._running = False
        if self._task:
            await self._task
            self._task = None
        logger.info("Message processor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Get next message from queue
                message = await message_queue.dequeue()

                if message:
                    await self._process_message(message)
                else:
                    # No messages, wait a bit
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in message processing loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait longer on error

    async def _process_message(self, queued_message: QueuedMessage) -> None:
        """Process a single message."""
        logger.info(
            f"Processing message {queued_message.id} for user {queued_message.user_id}"
        )

        try:
            # Create database session
            with SessionLocal() as db:
                # Create agent service
                agent_service = AgentService(db)

                # Process the message
                await agent_service.process_message(
                    user_id=queued_message.user_id,
                    message_content=queued_message.content,
                )

                # Acknowledge successful processing
                await message_queue.acknowledge(queued_message.id)
                logger.info(f"Successfully processed message {queued_message.id}")

        except Exception as e:
            logger.error(
                f"Error processing message {queued_message.id}: {e}", exc_info=True
            )

            # Retry the message
            retry_success = await message_queue.retry(queued_message, str(e))
            if not retry_success:
                logger.error(f"Message {queued_message.id} moved to failed queue")

    async def process_single(self) -> bool:
        """Process a single message (for testing/manual processing)."""
        message = await message_queue.dequeue()
        if message:
            await self._process_message(message)
            return True
        return False


# Global instance
message_processor = MessageProcessorService()
