"""Integration orchestrator to coordinate all WhatsApp integration components."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.config.private import settings
from app.services.bridge_config import bridge_config
from app.services.integration_monitor import integration_monitor
from app.services.message_processor import message_processor
from app.services.message_queue import message_queue

logger = logging.getLogger(__name__)


class IntegrationOrchestrator:
    """Orchestrate all WhatsApp integration components."""

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self._initialized = False
        self._processor_workers: list[asyncio.Task] = []
        self._worker_count = getattr(settings, "MESSAGE_PROCESSOR_WORKERS", 3)

    async def initialize(self) -> dict[str, Any]:
        """Initialize all integration components."""
        if self._initialized:
            logger.warning("Integration already initialized")
            return {"status": "already_initialized"}

        logger.info("Initializing WhatsApp integration...")
        results = {}

        try:
            # 1. Configure WhatsApp Bridge
            logger.info("Configuring WhatsApp Bridge...")
            bridge_result = await bridge_config.setup_bridge()
            results["bridge_config"] = bridge_result

            # 2. Ensure system session exists
            logger.info("Ensuring system WhatsApp session...")
            session_result = await bridge_config.ensure_system_session()
            results["system_session"] = session_result

            # 3. Start message processors
            logger.info(f"Starting {self._worker_count} message processor workers...")
            for i in range(self._worker_count):
                worker = asyncio.create_task(self._run_processor_worker(i))
                self._processor_workers.append(worker)
            results["message_processors"] = {"started": self._worker_count}

            # 4. Start integration monitor
            logger.info("Starting integration monitor...")
            await integration_monitor.start_monitoring(interval=30)
            results["monitor"] = {"status": "started", "interval": 30}

            # 5. Verify all components are healthy
            health = await integration_monitor.check_all_components()
            healthy_count = sum(1 for s in health.values() if s.healthy)
            total_count = len(health)

            results["health_check"] = {
                "healthy": healthy_count == total_count,
                "components": {
                    name: {"healthy": status.healthy, "details": status.details}
                    for name, status in health.items()
                },
            }

            self._initialized = True
            logger.info("WhatsApp integration initialized successfully")

            return {"status": "initialized", "results": results}

        except Exception as e:
            logger.error(f"Failed to initialize integration: {e}", exc_info=True)
            # Clean up any started components
            await self._cleanup()
            return {"status": "failed", "error": str(e), "partial_results": results}

    async def shutdown(self) -> dict[str, Any]:
        """Gracefully shutdown all integration components."""
        if not self._initialized:
            return {"status": "not_initialized"}

        logger.info("Shutting down WhatsApp integration...")

        try:
            # Stop components in reverse order
            await self._cleanup()

            self._initialized = False
            logger.info("WhatsApp integration shutdown complete")

            return {"status": "shutdown_complete"}

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            return {"status": "shutdown_error", "error": str(e)}

    async def _cleanup(self) -> None:
        """Clean up all started components."""
        # 1. Stop monitor
        await integration_monitor.stop_monitoring()

        # 2. Stop message processors
        for worker in self._processor_workers:
            worker.cancel()

        if self._processor_workers:
            await asyncio.gather(*self._processor_workers, return_exceptions=True)
        self._processor_workers.clear()

        # 3. Close message queue connection
        await message_queue.close()

    async def _run_processor_worker(self, worker_id: int) -> None:
        """Run a message processor worker."""
        logger.info(f"Message processor worker {worker_id} started")

        while True:
            try:
                # Process messages continuously
                processed = await message_processor.process_single()
                if not processed:
                    # No messages, wait a bit
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info(f"Message processor worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in processor worker {worker_id}: {e}", exc_info=True
                )
                await asyncio.sleep(5)  # Wait before retrying

    async def get_status(self) -> dict[str, Any]:
        """Get current status of the integration."""
        status = {
            "initialized": self._initialized,
            "workers": {
                "configured": self._worker_count,
                "running": len([w for w in self._processor_workers if not w.done()]),
            },
        }

        if self._initialized:
            # Get component health
            health = await integration_monitor.get_system_health()
            status["health"] = health

            # Get queue stats
            queue_stats = await message_queue.get_queue_stats()
            status["queue"] = queue_stats

            # Get bridge status
            bridge_health = await bridge_config.check_bridge_health()
            status["bridge"] = bridge_health

        return status

    async def reinitialize(self) -> dict[str, Any]:
        """Reinitialize the integration (shutdown and restart)."""
        logger.info("Reinitializing WhatsApp integration...")

        # Shutdown existing
        shutdown_result = await self.shutdown()

        # Wait a moment
        await asyncio.sleep(2)

        # Initialize again
        init_result = await self.initialize()

        return {"shutdown": shutdown_result, "initialize": init_result}

    @asynccontextmanager
    async def managed_integration(
        self,
    ) -> AsyncGenerator["IntegrationOrchestrator", None]:
        """Context manager for managed integration lifecycle."""
        try:
            await self.initialize()
            yield self
        finally:
            await self.shutdown()


# Global instance
integration_orchestrator = IntegrationOrchestrator()
