# Task 13: WhatsApp Bridge Integration with Zapw

## Objective
Integrate the zapw WhatsApp bridge service with our backend, including configuration, testing, and error handling.

## Prerequisites
- Backend API structure in place
- Understanding of zapw repository structure
- Docker environment ready

## Requirements
- Configure zapw as a submodule or Docker service
- Set up webhook communication
- Implement connection management
- Create integration tests
- Handle reconnection scenarios

## Integration Approach

### Option 1: Git Submodule
```bash
# Add zapw as submodule
git submodule add https://github.com/tonylampada/zapw.git whatsapp-bridge/zapw
git submodule update --init --recursive
```

### Option 2: Docker Image
```dockerfile
# whatsapp-bridge/Dockerfile
FROM node:18-alpine

WORKDIR /app

# Clone zapw repository
RUN apk add --no-cache git
RUN git clone https://github.com/tonylampada/zapw.git .

# Install dependencies
RUN npm install
RUN npm run build

# Create sessions directory
RUN mkdir -p sessions_data

EXPOSE 3000

CMD ["npm", "start"]
```

### docker-compose.yml (updated)
```yaml
version: '3.8'

services:
  whatsapp-bridge:
    build: ./whatsapp-bridge
    # or use pre-built image if available
    # image: tonylampada/zapw:latest
    environment:
      - PORT=3000
      - WEBHOOK_URL=http://backend:8000/api/v1/messages/webhook
      - WEBHOOK_AUTH_TOKEN=${WHATSAPP_API_KEY}
      - API_KEY=${WHATSAPP_API_KEY}
      - LOG_LEVEL=info
      - SESSION_DATA_PATH=/app/sessions_data
    volumes:
      - whatsapp_sessions:/app/sessions_data
    ports:
      - "3000:3000"  # Only for development
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/whatsapp_agent
      - WHATSAPP_API_URL=http://whatsapp-bridge:3000
      - WHATSAPP_API_KEY=${WHATSAPP_API_KEY}
    depends_on:
      - db
      - whatsapp-bridge
    networks:
      - app-network

volumes:
  whatsapp_sessions:

networks:
  app-network:
    driver: bridge
```

### backend/app/adapters/whatsapp_client.py (enhanced)
```python
import httpx
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime
from app.core.config import settings
from app.core.logging import logger

class WhatsAppClient:
    def __init__(self):
        self.base_url = settings.WHATSAPP_API_URL
        self.api_key = settings.WHATSAPP_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._health_check_interval = 60  # seconds
        self._last_health_check = None
    
    async def health_check(self) -> bool:
        """Check if WhatsApp Bridge is healthy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self.headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"WhatsApp Bridge health check failed: {str(e)}")
            return False
    
    async def wait_for_service(self, max_attempts: int = 10, delay: int = 5):
        """Wait for WhatsApp Bridge to be ready."""
        for attempt in range(max_attempts):
            if await self.health_check():
                logger.info("WhatsApp Bridge is ready")
                return True
            
            logger.warning(f"WhatsApp Bridge not ready, attempt {attempt + 1}/{max_attempts}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
        
        return False
    
    async def create_session(self, session_id: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WhatsApp session."""
        payload = {
            "id": session_id,
            "webhook": {
                "url": webhook_url or f"{settings.BACKEND_URL}/api/v1/messages/webhook",
                "events": [
                    "message.received",
                    "message.sent",
                    "message.delivered",
                    "message.read",
                    "session.connected",
                    "session.disconnected",
                    "session.qr"
                ]
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sessions",
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session status."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/sessions/{session_id}/status",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def reconnect_session(self, session_id: str) -> bool:
        """Attempt to reconnect a disconnected session."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/sessions/{session_id}/reconnect",
                    headers=self.headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to reconnect session {session_id}: {str(e)}")
            return False
```

### backend/tests/integration/test_whatsapp_integration.py
```python
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import docker
from app.adapters.whatsapp_client import WhatsAppClient

@pytest.fixture
async def whatsapp_service():
    """Start WhatsApp Bridge container for tests."""
    client = docker.from_env()
    
    # Start container
    container = client.containers.run(
        "tonylampada/zapw:latest",
        environment={
            "PORT": "3000",
            "API_KEY": "test-key",
            "WEBHOOK_URL": "http://backend:8000/api/v1/messages/webhook"
        },
        ports={'3000/tcp': 3001},
        detach=True,
        remove=True,
        name="test-whatsapp-bridge"
    )
    
    # Wait for service to be ready
    whatsapp_client = WhatsAppClient()
    whatsapp_client.base_url = "http://localhost:3001"
    
    ready = await whatsapp_client.wait_for_service(max_attempts=20)
    assert ready, "WhatsApp Bridge failed to start"
    
    yield whatsapp_client
    
    # Cleanup
    container.stop()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_session_integration(whatsapp_service):
    """Test creating a real session."""
    result = await whatsapp_service.create_session("test-session-1")
    
    assert "id" in result
    assert result["id"] == "test-session-1"
    assert "qr" in result or "qr_code" in result

@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_lifecycle(whatsapp_service):
    """Test full session lifecycle."""
    # Create session
    session_id = "test-lifecycle"
    await whatsapp_service.create_session(session_id)
    
    # Check status
    status = await whatsapp_service.get_session_status(session_id)
    assert status["status"] in ["qr_pending", "connecting"]
    
    # Delete session
    result = await whatsapp_service.delete_session(session_id)
    assert result is True
    
    # Verify deleted
    with pytest.raises(Exception):
        await whatsapp_service.get_session_status(session_id)
```

### backend/app/services/whatsapp_monitor.py
```python
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set
from sqlalchemy.orm import Session
from app.adapters.whatsapp_client import WhatsAppClient
from app.services.session_service import SessionService
from app.core.logging import logger

class WhatsAppMonitor:
    """Monitor WhatsApp Bridge health and session states."""
    
    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_client = WhatsAppClient()
        self.session_service = SessionService(db)
        self.check_interval = 60  # seconds
        self.reconnect_interval = 300  # 5 minutes
        self._running = False
        self._last_reconnect_attempt: Dict[str, datetime] = {}
    
    async def start(self):
        """Start monitoring."""
        self._running = True
        logger.info("WhatsApp Monitor started")
        
        while self._running:
            try:
                await self._check_health()
                await self._check_sessions()
            except Exception as e:
                logger.error(f"Monitor error: {str(e)}")
            
            await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """Stop monitoring."""
        self._running = False
        logger.info("WhatsApp Monitor stopped")
    
    async def _check_health(self):
        """Check WhatsApp Bridge health."""
        if not await self.whatsapp_client.health_check():
            logger.error("WhatsApp Bridge is not healthy!")
            # Could trigger alerts here
    
    async def _check_sessions(self):
        """Check and potentially reconnect sessions."""
        sessions = await self.session_service.get_active_sessions()
        
        for session in sessions:
            try:
                # Get actual status from bridge
                bridge_status = await self.whatsapp_client.get_session_status(session.id)
                
                # Update our records if different
                if bridge_status["status"] != session.status:
                    await self.session_service.update_session_status(
                        session.id,
                        bridge_status["status"]
                    )
                
                # Attempt reconnection if disconnected
                if bridge_status["status"] == "disconnected":
                    await self._try_reconnect(session.id)
                    
            except Exception as e:
                logger.error(f"Failed to check session {session.id}: {str(e)}")
    
    async def _try_reconnect(self, session_id: str):
        """Try to reconnect a session with rate limiting."""
        now = datetime.utcnow()
        last_attempt = self._last_reconnect_attempt.get(session_id)
        
        if last_attempt and (now - last_attempt).seconds < self.reconnect_interval:
            return  # Too soon to retry
        
        logger.info(f"Attempting to reconnect session {session_id}")
        self._last_reconnect_attempt[session_id] = now
        
        if await self.whatsapp_client.reconnect_session(session_id):
            logger.info(f"Successfully reconnected session {session_id}")
        else:
            logger.error(f"Failed to reconnect session {session_id}")
```

### backend/tests/test_whatsapp_monitor.py
```python
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from app.services.whatsapp_monitor import WhatsAppMonitor

@pytest.fixture
def monitor(db_session):
    return WhatsAppMonitor(db_session)

@pytest.mark.asyncio
async def test_monitor_health_check(monitor):
    """Test health check monitoring."""
    with patch.object(monitor.whatsapp_client, 'health_check') as mock_health:
        mock_health.return_value = True
        
        # Run one iteration
        monitor._running = True
        await monitor._check_health()
        
        mock_health.assert_called_once()

@pytest.mark.asyncio
async def test_monitor_session_reconnect(monitor, db_session):
    """Test session reconnection logic."""
    # Create test session
    from app.models.models import Session, Agent
    agent = Agent(name="Test", system_prompt="Test")
    db_session.add(agent)
    db_session.commit()
    
    session = Session(
        id="test-session",
        agent_id=agent.id,
        status="connected"
    )
    db_session.add(session)
    db_session.commit()
    
    # Mock methods
    with patch.object(monitor.session_service, 'get_active_sessions') as mock_get:
        mock_get.return_value = [session]
        
        with patch.object(monitor.whatsapp_client, 'get_session_status') as mock_status:
            mock_status.return_value = {"status": "disconnected"}
            
            with patch.object(monitor.whatsapp_client, 'reconnect_session') as mock_reconnect:
                mock_reconnect.return_value = True
                
                await monitor._check_sessions()
                
                mock_reconnect.assert_called_once_with("test-session")

@pytest.mark.asyncio
async def test_monitor_reconnect_rate_limiting(monitor):
    """Test that reconnection attempts are rate limited."""
    session_id = "test-session"
    
    # First attempt
    monitor._last_reconnect_attempt[session_id] = datetime.utcnow()
    
    with patch.object(monitor.whatsapp_client, 'reconnect_session') as mock_reconnect:
        # Should not reconnect (too soon)
        await monitor._try_reconnect(session_id)
        mock_reconnect.assert_not_called()
        
        # Simulate time passing
        monitor._last_reconnect_attempt[session_id] = datetime.utcnow() - timedelta(minutes=10)
        
        # Should reconnect now
        await monitor._try_reconnect(session_id)
        mock_reconnect.assert_called_once()
```

### Integration with Backend Startup

### backend/app/main.py (updated)
```python
from contextlib import asynccontextmanager
from app.services.whatsapp_monitor import WhatsAppMonitor

# Background tasks
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting WhatsApp Agent Backend")
    
    # Wait for WhatsApp Bridge
    whatsapp_client = WhatsAppClient()
    if not await whatsapp_client.wait_for_service():
        logger.error("WhatsApp Bridge is not available!")
    
    # Start monitor
    db = SessionLocal()
    monitor = WhatsAppMonitor(db)
    monitor_task = asyncio.create_task(monitor.start())
    background_tasks.append(monitor_task)
    
    yield
    
    # Shutdown
    logger.info("Shutting down WhatsApp Agent Backend")
    await monitor.stop()
    for task in background_tasks:
        task.cancel()
    db.close()

app = FastAPI(
    title="WhatsApp Agent API",
    version="1.0.0",
    lifespan=lifespan
)
```

## Success Criteria
- [ ] WhatsApp Bridge integrated via Docker
- [ ] Webhook communication working
- [ ] Session persistence across restarts
- [ ] Health monitoring implemented
- [ ] Automatic reconnection logic
- [ ] Integration tests passing
- [ ] Error handling for bridge failures

## Commands to Run
```bash
# Build WhatsApp Bridge image
cd whatsapp-bridge
docker build -t whatsapp-bridge .

# Run integration tests
cd backend
uv run pytest tests/integration/test_whatsapp_integration.py -v -m integration

# Run with docker-compose
docker-compose up whatsapp-bridge backend

# Check bridge health
curl http://localhost:3000/health

# View bridge logs
docker-compose logs -f whatsapp-bridge
```