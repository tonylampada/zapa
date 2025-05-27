# Task 13: WhatsApp Bridge Integration

## Overview
Complete the integration between Zapa services and the WhatsApp Bridge (zapw). This connects all the pieces to enable end-to-end message flow from WhatsApp users through AI processing and back.

## Prerequisites
- Task 06: WhatsApp Bridge Adapter
- Task 09: Agent Service with LLM Tools
- Task 11: Webhook Handlers
- Task 12: Public Auth Flow (for sending auth codes)

## Acceptance Criteria
1. Configure Bridge to send webhooks to Zapa Private
2. Handle all Bridge event types properly
3. Implement message queuing for reliability
4. Add health checks and monitoring
5. Handle Bridge disconnections gracefully
6. Support multiple concurrent sessions
7. Implement proper error recovery
8. Add integration test suite

## Test-Driven Development Steps

### Step 1: Create Bridge Configuration Service
```python
# backend/app/services/bridge_config.py
from typing import Dict, Optional, List
from dataclasses import dataclass
from app.adapters.whatsapp import WhatsAppBridgeAdapter
import logging

logger = logging.getLogger(__name__)

@dataclass
class BridgeConfig:
    webhook_url: str
    webhook_secret: Optional[str]
    retry_attempts: int = 3
    retry_delay: int = 5
    health_check_interval: int = 30

class BridgeConfigurationService:
    """Manages WhatsApp Bridge configuration and health."""
    
    def __init__(
        self, 
        bridge_adapter: WhatsAppBridgeAdapter,
        config: BridgeConfig
    ):
        self.bridge = bridge_adapter
        self.config = config
        self._health_check_task = None
        
    async def configure_bridge(self) -> bool:
        """Configure the Bridge with our webhook endpoint."""
        try:
            # Set webhook configuration
            result = await self.bridge.configure_webhook(
                url=self.config.webhook_url,
                events=[
                    "message.received",
                    "message.sent",
                    "message.failed",
                    "connection.status"
                ],
                secret=self.config.webhook_secret
            )
            
            if result:
                logger.info(f"Bridge configured with webhook: {self.config.webhook_url}")
                return True
            else:
                logger.error("Failed to configure Bridge webhook")
                return False
                
        except Exception as e:
            logger.error(f"Bridge configuration error: {e}")
            return False
    
    async def get_bridge_status(self) -> Dict:
        """Get current Bridge status and sessions."""
        try:
            status = await self.bridge.get_status()
            sessions = await self.bridge.get_sessions()
            
            return {
                "connected": status.get("connected", False),
                "uptime": status.get("uptime", 0),
                "version": status.get("version", "unknown"),
                "sessions": sessions,
                "session_count": len(sessions)
            }
        except Exception as e:
            logger.error(f"Failed to get Bridge status: {e}")
            return {
                "connected": False,
                "error": str(e)
            }
    
    async def ensure_session(self, phone_number: str) -> bool:
        """Ensure a WhatsApp session exists for the phone number."""
        try:
            # Check if session exists
            sessions = await self.bridge.get_sessions()
            
            for session in sessions:
                if session.get("phone_number") == phone_number:
                    if session.get("status") == "connected":
                        return True
                    else:
                        # Try to reconnect
                        return await self.bridge.reconnect_session(
                            session["session_id"]
                        )
            
            # No session found - this would require QR code scanning
            # In production, this would trigger a notification to admin
            logger.warning(f"No session found for {phone_number}")
            return False
            
        except Exception as e:
            logger.error(f"Session check failed: {e}")
            return False
```

**Tests:**
```python
# backend/tests/unit/services/test_bridge_config.py
@pytest.mark.asyncio
async def test_configure_bridge(mock_bridge_adapter):
    config = BridgeConfig(
        webhook_url="https://api.zapa.com/webhooks/whatsapp",
        webhook_secret="test_secret"
    )
    
    service = BridgeConfigurationService(mock_bridge_adapter, config)
    mock_bridge_adapter.configure_webhook.return_value = True
    
    result = await service.configure_bridge()
    
    assert result is True
    mock_bridge_adapter.configure_webhook.assert_called_once_with(
        url=config.webhook_url,
        events=["message.received", "message.sent", "message.failed", "connection.status"],
        secret=config.webhook_secret
    )

@pytest.mark.asyncio
async def test_get_bridge_status(mock_bridge_adapter):
    service = BridgeConfigurationService(
        mock_bridge_adapter,
        BridgeConfig(webhook_url="test")
    )
    
    mock_bridge_adapter.get_status.return_value = {
        "connected": True,
        "uptime": 3600
    }
    mock_bridge_adapter.get_sessions.return_value = [
        {"session_id": "123", "phone_number": "+1234567890", "status": "connected"}
    ]
    
    status = await service.get_bridge_status()
    
    assert status["connected"] is True
    assert status["session_count"] == 1
    assert len(status["sessions"]) == 1
```

### Step 2: Create Message Queue for Reliability
```python
# backend/app/services/message_queue.py
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import asyncio
import json
from redis import Redis
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class QueuedMessage:
    id: str
    to_number: str
    content: str
    from_number: Optional[str] = None
    media_url: Optional[str] = None
    priority: int = 0
    created_at: datetime = None
    attempts: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

class MessageQueueService:
    """Reliable message queue for WhatsApp sending."""
    
    def __init__(
        self,
        redis_client: Redis,
        bridge_adapter: WhatsAppBridgeAdapter,
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        self.redis = redis_client
        self.bridge = bridge_adapter
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.queue_key = "whatsapp:outbound:queue"
        self.processing_key = "whatsapp:outbound:processing"
        self._worker_task = None
        
    async def enqueue_message(
        self,
        to_number: str,
        content: str,
        from_number: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """Add message to send queue."""
        import uuid
        
        message = QueuedMessage(
            id=str(uuid.uuid4()),
            to_number=to_number,
            content=content,
            from_number=from_number,
            priority=priority
        )
        
        # Use priority queue (sorted set)
        score = -priority * 1000000 + message.created_at.timestamp()
        
        await self.redis.zadd(
            self.queue_key,
            {json.dumps(asdict(message)): score}
        )
        
        logger.info(f"Enqueued message {message.id} to {to_number}")
        return message.id
    
    async def start_worker(self):
        """Start background worker to process queue."""
        if self._worker_task:
            return
            
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("Message queue worker started")
    
    async def stop_worker(self):
        """Stop the queue worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Message queue worker stopped")
    
    async def _process_queue(self):
        """Process messages from queue."""
        while True:
            try:
                # Get highest priority message
                messages = await self.redis.zrange(
                    self.queue_key, 0, 0, withscores=True
                )
                
                if not messages:
                    await asyncio.sleep(1)
                    continue
                
                message_data, score = messages[0]
                message_dict = json.loads(message_data)
                message = QueuedMessage(**message_dict)
                
                # Move to processing
                await self.redis.zrem(self.queue_key, message_data)
                await self.redis.hset(
                    self.processing_key,
                    message.id,
                    message_data
                )
                
                # Try to send
                success = await self._send_with_retry(message)
                
                # Clean up
                await self.redis.hdel(self.processing_key, message.id)
                
                if not success:
                    logger.error(f"Failed to send message {message.id} after retries")
                    # Could move to dead letter queue here
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(5)
    
    async def _send_with_retry(self, message: QueuedMessage) -> bool:
        """Send message with retries."""
        for attempt in range(self.max_retries):
            try:
                result = await self.bridge.send_message(
                    to_number=message.to_number,
                    message=message.content,
                    from_number=message.from_number,
                    media_url=message.media_url
                )
                
                if result and result.get("message_id"):
                    logger.info(f"Sent message {message.id} successfully")
                    return True
                    
            except Exception as e:
                logger.warning(
                    f"Send attempt {attempt + 1} failed for {message.id}: {e}"
                )
                
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return False
    
    async def get_queue_stats(self) -> Dict:
        """Get queue statistics."""
        queue_size = await self.redis.zcard(self.queue_key)
        processing_size = await self.redis.hlen(self.processing_key)
        
        return {
            "queued": queue_size,
            "processing": processing_size,
            "total": queue_size + processing_size
        }
```

**Tests:**
```python
# backend/tests/unit/services/test_message_queue.py
@pytest.mark.asyncio
async def test_enqueue_message(mock_redis, mock_bridge):
    queue = MessageQueueService(mock_redis, mock_bridge)
    
    message_id = await queue.enqueue_message(
        to_number="+1234567890",
        content="Test message",
        priority=1
    )
    
    assert message_id is not None
    mock_redis.zadd.assert_called_once()

@pytest.mark.asyncio
async def test_message_processing(mock_redis, mock_bridge):
    queue = MessageQueueService(
        mock_redis, 
        mock_bridge,
        max_retries=2,
        retry_delay=0
    )
    
    # Simulate queued message
    message_data = json.dumps({
        "id": "test-123",
        "to_number": "+1234567890",
        "content": "Test",
        "from_number": None,
        "media_url": None,
        "priority": 0,
        "created_at": datetime.utcnow().isoformat(),
        "attempts": 0
    })
    
    mock_redis.zrange.return_value = [(message_data, 1.0)]
    mock_bridge.send_message.return_value = {"message_id": "wa_123"}
    
    # Process one message
    await queue._process_queue()
    
    mock_bridge.send_message.assert_called_once()
    mock_redis.zrem.assert_called_once()
    mock_redis.hdel.assert_called_once()
```

### Step 3: Create Integration Monitoring Service
```python
# backend/app/services/integration_monitor.py
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class ComponentStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheck:
    component: str
    status: ComponentStatus
    message: str
    last_check: datetime
    metadata: Optional[Dict] = None

class IntegrationMonitor:
    """Monitor health of all integration points."""
    
    def __init__(
        self,
        bridge_config: BridgeConfigurationService,
        message_queue: MessageQueueService,
        redis_client: Redis
    ):
        self.bridge_config = bridge_config
        self.message_queue = message_queue
        self.redis = redis_client
        self.health_checks: Dict[str, HealthCheck] = {}
        self._monitor_task = None
        
    async def start_monitoring(self, interval: int = 30):
        """Start health monitoring."""
        if self._monitor_task:
            return
            
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(interval)
        )
        logger.info("Integration monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    async def _monitor_loop(self, interval: int):
        """Run health checks periodically."""
        while True:
            try:
                await self.check_all_components()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(interval)
    
    async def check_all_components(self) -> Dict[str, HealthCheck]:
        """Check health of all components."""
        checks = await asyncio.gather(
            self._check_whatsapp_bridge(),
            self._check_message_queue(),
            self._check_redis(),
            return_exceptions=True
        )
        
        for check in checks:
            if isinstance(check, HealthCheck):
                self.health_checks[check.component] = check
            elif isinstance(check, Exception):
                logger.error(f"Health check failed: {check}")
        
        return self.health_checks
    
    async def _check_whatsapp_bridge(self) -> HealthCheck:
        """Check WhatsApp Bridge health."""
        try:
            status = await self.bridge_config.get_bridge_status()
            
            if status.get("connected"):
                session_count = status.get("session_count", 0)
                if session_count > 0:
                    return HealthCheck(
                        component="whatsapp_bridge",
                        status=ComponentStatus.HEALTHY,
                        message=f"Connected with {session_count} sessions",
                        last_check=datetime.utcnow(),
                        metadata=status
                    )
                else:
                    return HealthCheck(
                        component="whatsapp_bridge",
                        status=ComponentStatus.DEGRADED,
                        message="Connected but no active sessions",
                        last_check=datetime.utcnow(),
                        metadata=status
                    )
            else:
                return HealthCheck(
                    component="whatsapp_bridge",
                    status=ComponentStatus.UNHEALTHY,
                    message="Bridge not connected",
                    last_check=datetime.utcnow(),
                    metadata=status
                )
                
        except Exception as e:
            return HealthCheck(
                component="whatsapp_bridge",
                status=ComponentStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_message_queue(self) -> HealthCheck:
        """Check message queue health."""
        try:
            stats = await self.message_queue.get_queue_stats()
            total = stats.get("total", 0)
            
            if total < 100:
                status = ComponentStatus.HEALTHY
                message = f"{total} messages in queue"
            elif total < 500:
                status = ComponentStatus.DEGRADED
                message = f"High queue size: {total} messages"
            else:
                status = ComponentStatus.UNHEALTHY
                message = f"Critical queue size: {total} messages"
            
            return HealthCheck(
                component="message_queue",
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                metadata=stats
            )
            
        except Exception as e:
            return HealthCheck(
                component="message_queue",
                status=ComponentStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_redis(self) -> HealthCheck:
        """Check Redis health."""
        try:
            # Simple ping
            await self.redis.ping()
            
            # Check memory usage
            info = await self.redis.info("memory")
            used_memory = info.get("used_memory_human", "unknown")
            
            return HealthCheck(
                component="redis",
                status=ComponentStatus.HEALTHY,
                message=f"Connected, memory: {used_memory}",
                last_check=datetime.utcnow(),
                metadata={"memory": used_memory}
            )
            
        except Exception as e:
            return HealthCheck(
                component="redis",
                status=ComponentStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    def get_overall_health(self) -> ComponentStatus:
        """Get overall system health status."""
        if not self.health_checks:
            return ComponentStatus.UNHEALTHY
        
        statuses = [check.status for check in self.health_checks.values()]
        
        if all(s == ComponentStatus.HEALTHY for s in statuses):
            return ComponentStatus.HEALTHY
        elif any(s == ComponentStatus.UNHEALTHY for s in statuses):
            return ComponentStatus.UNHEALTHY
        else:
            return ComponentStatus.DEGRADED
```

### Step 4: Create Integration Orchestrator
```python
# backend/app/services/integration_orchestrator.py
from typing import Optional
from app.services.bridge_config import (
    BridgeConfigurationService,
    BridgeConfig
)
from app.services.message_queue import MessageQueueService
from app.services.integration_monitor import IntegrationMonitor
from app.adapters.whatsapp import WhatsAppBridgeAdapter
import logging

logger = logging.getLogger(__name__)

class WhatsAppIntegrationOrchestrator:
    """Orchestrates all WhatsApp integration components."""
    
    def __init__(
        self,
        bridge_adapter: WhatsAppBridgeAdapter,
        redis_client: Redis,
        webhook_url: str,
        webhook_secret: Optional[str] = None
    ):
        # Initialize configuration
        self.bridge_config = BridgeConfigurationService(
            bridge_adapter,
            BridgeConfig(
                webhook_url=webhook_url,
                webhook_secret=webhook_secret
            )
        )
        
        # Initialize message queue
        self.message_queue = MessageQueueService(
            redis_client,
            bridge_adapter
        )
        
        # Initialize monitoring
        self.monitor = IntegrationMonitor(
            self.bridge_config,
            self.message_queue,
            redis_client
        )
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all integration components."""
        if self._initialized:
            return True
        
        try:
            # Configure Bridge
            if not await self.bridge_config.configure_bridge():
                logger.error("Failed to configure WhatsApp Bridge")
                return False
            
            # Start message queue worker
            await self.message_queue.start_worker()
            
            # Start health monitoring
            await self.monitor.start_monitoring()
            
            self._initialized = True
            logger.info("WhatsApp integration initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Integration initialization failed: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown all integration components."""
        logger.info("Shutting down WhatsApp integration...")
        
        # Stop monitoring first
        await self.monitor.stop_monitoring()
        
        # Stop message queue
        await self.message_queue.stop_worker()
        
        self._initialized = False
        logger.info("WhatsApp integration shutdown complete")
    
    async def send_message(
        self,
        to_number: str,
        content: str,
        from_number: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """Send message through the integration."""
        if not self._initialized:
            raise RuntimeError("Integration not initialized")
        
        # Check if we have a session for the target number
        if from_number and not await self.bridge_config.ensure_session(from_number):
            logger.warning(f"No session available for {from_number}")
            # Still queue the message - session might come online
        
        # Queue the message
        message_id = await self.message_queue.enqueue_message(
            to_number=to_number,
            content=content,
            from_number=from_number,
            priority=priority
        )
        
        return message_id
    
    async def get_health_status(self) -> Dict:
        """Get current health status of integration."""
        checks = await self.monitor.check_all_components()
        overall = self.monitor.get_overall_health()
        
        return {
            "overall_status": overall.value,
            "components": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "last_check": check.last_check.isoformat(),
                    "metadata": check.metadata
                }
                for name, check in checks.items()
            }
        }
```

### Step 5: Add Integration API Endpoints
```python
# backend/app/private/api/v1/integration.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from app.services.integration_orchestrator import (
    WhatsAppIntegrationOrchestrator
)
from app.core.dependencies import (
    get_integration_orchestrator,
    require_admin
)

router = APIRouter(
    prefix="/integration",
    tags=["integration"],
    dependencies=[Depends(require_admin)]
)

@router.get("/health", response_model=Dict)
async def get_integration_health(
    orchestrator: WhatsAppIntegrationOrchestrator = Depends(
        get_integration_orchestrator
    )
):
    """Get health status of WhatsApp integration."""
    return await orchestrator.get_health_status()

@router.post("/reinitialize")
async def reinitialize_integration(
    orchestrator: WhatsAppIntegrationOrchestrator = Depends(
        get_integration_orchestrator
    )
):
    """Reinitialize WhatsApp integration."""
    await orchestrator.shutdown()
    
    if await orchestrator.initialize():
        return {"status": "success", "message": "Integration reinitialized"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to reinitialize integration"
        )

@router.get("/queue/stats", response_model=Dict)
async def get_queue_statistics(
    orchestrator: WhatsAppIntegrationOrchestrator = Depends(
        get_integration_orchestrator
    )
):
    """Get message queue statistics."""
    return await orchestrator.message_queue.get_queue_stats()
```

### Step 6: Create Integration Tests
```python
# backend/tests/integration/services/test_whatsapp_integration.py
import pytest
import asyncio
from datetime import datetime

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_WHATSAPP", "false").lower() != "true",
    reason="WhatsApp integration tests disabled"
)
class TestWhatsAppIntegration:
    
    @pytest.mark.asyncio
    async def test_full_message_flow(
        self,
        integration_orchestrator,
        test_phone_number
    ):
        """Test complete message send flow."""
        # Initialize integration
        assert await integration_orchestrator.initialize()
        
        # Send a message
        message_id = await integration_orchestrator.send_message(
            to_number=test_phone_number,
            content="Integration test message",
            priority=1
        )
        
        assert message_id is not None
        
        # Wait for processing
        await asyncio.sleep(5)
        
        # Check queue stats
        stats = await integration_orchestrator.message_queue.get_queue_stats()
        assert stats["total"] == 0  # Message should be sent
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, integration_orchestrator):
        """Test health monitoring functionality."""
        await integration_orchestrator.initialize()
        
        # Get health status
        health = await integration_orchestrator.get_health_status()
        
        assert health["overall_status"] in ["healthy", "degraded", "unhealthy"]
        assert "whatsapp_bridge" in health["components"]
        assert "message_queue" in health["components"]
        assert "redis" in health["components"]
    
    @pytest.mark.asyncio
    async def test_message_retry_on_failure(
        self,
        integration_orchestrator,
        mock_bridge_failure
    ):
        """Test message retry logic."""
        await integration_orchestrator.initialize()
        
        # Configure bridge to fail first 2 attempts
        mock_bridge_failure.fail_count = 2
        
        message_id = await integration_orchestrator.send_message(
            to_number="+1234567890",
            content="Test retry"
        )
        
        # Wait for retries
        await asyncio.sleep(10)
        
        # Should succeed on 3rd attempt
        assert mock_bridge_failure.send_count == 3
```

## Implementation Notes

1. **Reliability**:
   - Message queue ensures no messages are lost
   - Automatic retries with exponential backoff
   - Health monitoring for early problem detection
   - Graceful degradation when components fail

2. **Performance**:
   - Async processing throughout
   - Priority queue for urgent messages
   - Connection pooling for Redis
   - Efficient webhook handling

3. **Monitoring**:
   - Component-level health checks
   - Queue depth monitoring
   - Integration test suite
   - Detailed logging

4. **Security**:
   - Webhook signature validation
   - Network isolation between services
   - No sensitive data in logs

## Dependencies
- WhatsApp Bridge (zapw)
- Redis for message queuing
- AsyncIO for concurrent processing
- FastAPI for monitoring endpoints

## Next Steps
- Task 14: Frontend User Dashboard
- Task 15: Vue.js Frontend Setup