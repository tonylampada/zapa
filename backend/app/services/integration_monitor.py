"""Integration monitoring service for health checks."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis
from sqlalchemy import text

from app.config.redis import redis_settings
from app.core.database import SessionLocal
from app.services.bridge_config import bridge_config
from app.services.message_queue import message_queue

logger = logging.getLogger(__name__)


class ComponentStatus:
    """Status of a system component."""

    def __init__(self, name: str, healthy: bool, details: dict[str, Any] | None = None):
        self.name = name
        self.healthy = healthy
        self.details = details or {}
        self.checked_at = datetime.now(timezone.utc)


class IntegrationMonitor:
    """Monitor health and status of all integration components."""

    def __init__(self) -> None:
        """Initialize the integration monitor."""
        self._monitoring_task: asyncio.Task | None = None
        self._running = False
        self._last_status: dict[str, ComponentStatus] = {}

    async def start_monitoring(self, interval: int = 60) -> None:
        """Start continuous health monitoring."""
        if self._running:
            logger.warning("Integration monitor is already running")
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f"Integration monitor started with {interval}s interval")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._running = False
        if self._monitoring_task:
            await self._monitoring_task
            self._monitoring_task = None
        logger.info("Integration monitor stopped")

    async def _monitor_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self.check_all_components()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(interval)

    async def check_all_components(self) -> dict[str, ComponentStatus]:
        """Check health of all system components."""
        results = {}

        # Check each component
        checks = [
            ("database", self._check_database),
            ("redis", self._check_redis),
            ("whatsapp_bridge", self._check_whatsapp_bridge),
            ("message_queue", self._check_message_queue),
        ]

        # Run all checks concurrently
        check_tasks = [self._run_check(name, check_func) for name, check_func in checks]
        statuses = await asyncio.gather(*check_tasks, return_exceptions=True)

        # Process results
        for (name, _), status in zip(checks, statuses, strict=False):
            if isinstance(status, BaseException):
                results[name] = ComponentStatus(name, False, {"error": str(status)})
            elif isinstance(status, ComponentStatus):
                results[name] = status
            else:
                # Shouldn't happen, but handle it gracefully
                results[name] = ComponentStatus(name, False, {"error": "Unknown status type"})

        # Update last status
        self._last_status = results

        # Log overall health
        healthy_count = sum(1 for s in results.values() if s.healthy)
        total_count = len(results)
        overall_health = "healthy" if healthy_count == total_count else "degraded"

        logger.info(
            f"Integration health check: {overall_health} "
            f"({healthy_count}/{total_count} components healthy)"
        )

        return results

    async def _run_check(self, name: str, check_func: Any) -> ComponentStatus:
        """Run a single health check with error handling."""
        try:
            result = await check_func()
            if not isinstance(result, ComponentStatus):
                raise TypeError(f"Check function {check_func.__name__} did not return ComponentStatus")
            return result
        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            return ComponentStatus(name, False, {"error": str(e)})

    async def _check_database(self) -> ComponentStatus:
        """Check database connectivity."""
        try:
            with SessionLocal() as db:
                # Simple query to verify connection
                result = db.execute(text("SELECT 1"))
                result.scalar()

                # Get some basic stats
                user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
                message_count = db.execute(text("SELECT COUNT(*) FROM messages")).scalar()

                return ComponentStatus(
                    "database",
                    True,
                    {
                        "users": user_count,
                        "messages": message_count,
                        "connection": "established",
                    },
                )
        except Exception as e:
            return ComponentStatus("database", False, {"error": str(e)})

    async def _check_redis(self) -> ComponentStatus:
        """Check Redis connectivity."""
        try:
            redis_client = await redis.from_url(
                redis_settings.redis_url,
                decode_responses=True,
                socket_timeout=5.0,
            )

            # Ping Redis
            await redis_client.ping()

            # Get memory info
            info = await redis_client.info("memory")

            await redis_client.close()

            return ComponentStatus(
                "redis",
                True,
                {
                    "connection": "established",
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                },
            )
        except Exception as e:
            return ComponentStatus("redis", False, {"error": str(e)})

    async def _check_whatsapp_bridge(self) -> ComponentStatus:
        """Check WhatsApp Bridge health."""
        try:
            health = await bridge_config.check_bridge_health()

            is_healthy = health.get("status") == "healthy"

            return ComponentStatus(
                "whatsapp_bridge",
                is_healthy,
                {
                    "total_sessions": health.get("total_sessions", 0),
                    "active_sessions": health.get("active_sessions", 0),
                    "bridge_url": health.get("bridge_url", "unknown"),
                    "error": health.get("error") if not is_healthy else None,
                },
            )
        except Exception as e:
            return ComponentStatus("whatsapp_bridge", False, {"error": str(e)})

    async def _check_message_queue(self) -> ComponentStatus:
        """Check message queue status."""
        try:
            stats = await message_queue.get_queue_stats()

            # Consider unhealthy if too many messages are queued or failed
            total_queued = stats["total"] - stats["failed"]
            is_healthy = (
                stats["failed"] < 100  # Less than 100 failed messages
                and total_queued < 1000  # Less than 1000 messages in queue
            )

            return ComponentStatus(
                "message_queue",
                is_healthy,
                {
                    "queues": stats["queues"],
                    "processing": stats["processing"],
                    "failed": stats["failed"],
                    "total": stats["total"],
                    "healthy": is_healthy,
                },
            )
        except Exception as e:
            return ComponentStatus("message_queue", False, {"error": str(e)})

    async def get_system_health(self) -> dict[str, Any]:
        """Get overall system health summary."""
        # Get latest status or check now if none available
        if not self._last_status:
            await self.check_all_components()

        # Calculate overall health
        healthy_components = [s for s in self._last_status.values() if s.healthy]
        unhealthy_components = [s for s in self._last_status.values() if not s.healthy]

        overall_healthy = len(unhealthy_components) == 0

        return {
            "healthy": overall_healthy,
            "status": "healthy" if overall_healthy else "degraded",
            "components": {
                name: {
                    "healthy": status.healthy,
                    "details": status.details,
                    "checked_at": status.checked_at.isoformat(),
                }
                for name, status in self._last_status.items()
            },
            "summary": {
                "total_components": len(self._last_status),
                "healthy_components": len(healthy_components),
                "unhealthy_components": len(unhealthy_components),
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_component_health(self, component: str) -> dict[str, Any] | None:
        """Get health status for a specific component."""
        status = self._last_status.get(component)
        if not status:
            return None

        return {
            "name": status.name,
            "healthy": status.healthy,
            "details": status.details,
            "checked_at": status.checked_at.isoformat(),
        }


# Global instance
integration_monitor = IntegrationMonitor()
