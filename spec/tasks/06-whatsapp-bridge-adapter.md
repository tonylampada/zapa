# Task 06: WhatsApp Bridge Adapter with Integration Tests

## Objective
Create the WhatsApp Bridge adapter that communicates with the zapw service, including both unit tests (with mocks) and integration tests (skippable).

## Prerequisites
- Tasks 01-05 completed
- zapw WhatsApp Bridge running on port 3000 (for integration tests)
- All previous tests passing in CI/CD

## Success Criteria
- [ ] WhatsApp Bridge adapter implemented
- [ ] Unit tests with mocked responses
- [ ] Integration tests that can be skipped by default
- [ ] Error handling for connection failures
- [ ] Tests passing locally and in CI/CD
- [ ] Code coverage ≥ 90%

## Files to Create

### services/private/app/adapters/__init__.py
```python
from .whatsapp import WhatsAppBridge, WhatsAppBridgeError

__all__ = ["WhatsAppBridge", "WhatsAppBridgeError"]
```

### services/private/app/adapters/whatsapp.py
```python
"""WhatsApp Bridge adapter for zapw service."""
import httpx
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WhatsAppBridgeError(Exception):
    """Base exception for WhatsApp Bridge errors."""
    pass


class ConnectionError(WhatsAppBridgeError):
    """Connection error to WhatsApp Bridge."""
    pass


class SessionError(WhatsAppBridgeError):
    """Session-related error."""
    pass


# Pydantic models for WhatsApp Bridge API

class QRCodeResponse(BaseModel):
    """QR code response from bridge."""
    qr_code: str
    timeout: int = Field(default=60, description="Seconds until QR expires")


class SessionStatus(BaseModel):
    """Session status from bridge."""
    session_id: str
    status: str  # "qr_pending", "connected", "disconnected", "error"
    phone_number: Optional[str] = None
    connected_at: Optional[datetime] = None
    error: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    session_id: str
    recipient_jid: str
    content: str
    quoted_message_id: Optional[str] = None


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: str
    timestamp: datetime
    status: str = "sent"


class IncomingMessage(BaseModel):
    """Incoming message from webhook."""
    session_id: str
    message_id: str
    sender_jid: str
    recipient_jid: str
    timestamp: datetime
    message_type: str
    content: Optional[str] = None
    caption: Optional[str] = None
    media_url: Optional[str] = None
    quoted_message_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WhatsAppBridge:
    """Adapter for zapw WhatsApp Bridge service."""
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        webhook_url: Optional[str] = None,
    ):
        """
        Initialize WhatsApp Bridge adapter.
        
        Args:
            base_url: Base URL of zapw service (e.g., http://localhost:3000)
            timeout: Request timeout in seconds
            webhook_url: URL for zapw to send webhooks to
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.webhook_url = webhook_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if not self._client:
            raise RuntimeError("WhatsAppBridge must be used as async context manager")
        return self._client
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if WhatsApp Bridge is healthy."""
        try:
            response = await self.client.get("/health")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Health check failed: {e}")
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def create_session(self, session_id: str) -> SessionStatus:
        """
        Create a new WhatsApp session.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            SessionStatus with current status
        """
        try:
            payload = {
                "session_id": session_id,
                "webhook_url": self.webhook_url,
            }
            response = await self.client.post("/sessions", json=payload)
            response.raise_for_status()
            return SessionStatus(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise SessionError(f"Session {session_id} already exists")
            raise SessionError(f"Failed to create session: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def get_session_status(self, session_id: str) -> SessionStatus:
        """Get status of a WhatsApp session."""
        try:
            response = await self.client.get(f"/sessions/{session_id}")
            response.raise_for_status()
            return SessionStatus(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SessionError(f"Session {session_id} not found")
            raise SessionError(f"Failed to get session status: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def get_qr_code(self, session_id: str) -> QRCodeResponse:
        """
        Get QR code for session authentication.
        
        Args:
            session_id: Session to get QR code for
            
        Returns:
            QRCodeResponse with base64 QR code
        """
        try:
            response = await self.client.get(f"/sessions/{session_id}/qr")
            response.raise_for_status()
            return QRCodeResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SessionError(f"Session {session_id} not found")
            if e.response.status_code == 400:
                raise SessionError("Session already connected")
            raise SessionError(f"Failed to get QR code: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def send_message(
        self,
        session_id: str,
        recipient: str,
        content: str,
        quoted_message_id: Optional[str] = None,
    ) -> SendMessageResponse:
        """
        Send a text message.
        
        Args:
            session_id: Session to send from
            recipient: Recipient phone number (with country code)
            content: Message content
            quoted_message_id: Optional message ID to quote/reply to
            
        Returns:
            SendMessageResponse with message details
        """
        # Ensure recipient has WhatsApp suffix
        if not recipient.endswith("@s.whatsapp.net"):
            recipient = f"{recipient}@s.whatsapp.net"
        
        try:
            request = SendMessageRequest(
                session_id=session_id,
                recipient_jid=recipient,
                content=content,
                quoted_message_id=quoted_message_id,
            )
            response = await self.client.post(
                f"/sessions/{session_id}/messages",
                json=request.model_dump(exclude_none=True),
            )
            response.raise_for_status()
            return SendMessageResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SessionError(f"Session {session_id} not found")
            if e.response.status_code == 400:
                raise SessionError("Session not connected")
            raise WhatsAppBridgeError(f"Failed to send message: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete/disconnect a WhatsApp session.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            response = await self.client.delete(f"/sessions/{session_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False  # Already deleted
            raise SessionError(f"Failed to delete session: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
    
    async def list_sessions(self) -> List[SessionStatus]:
        """List all active sessions."""
        try:
            response = await self.client.get("/sessions")
            response.raise_for_status()
            sessions_data = response.json()
            return [SessionStatus(**session) for session in sessions_data]
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}")
```

### services/private/tests/adapters/__init__.py
```python
# Empty file to make adapters a package
```

### services/private/tests/adapters/test_whatsapp_unit.py
```python
"""Unit tests for WhatsApp Bridge adapter with mocked responses."""
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from datetime import datetime

from app.adapters.whatsapp import (
    WhatsAppBridge,
    WhatsAppBridgeError,
    ConnectionError,
    SessionError,
    QRCodeResponse,
    SessionStatus,
    SendMessageResponse,
)


@pytest.fixture
async def bridge():
    """Create WhatsApp Bridge instance."""
    async with WhatsAppBridge(
        base_url="http://localhost:3000",
        webhook_url="http://localhost:8001/webhooks/whatsapp",
    ) as bridge:
        yield bridge


@pytest.fixture
def mock_response():
    """Create a mock response."""
    def _mock_response(json_data=None, status_code=200):
        response = AsyncMock()
        response.json.return_value = json_data or {}
        response.status_code = status_code
        response.raise_for_status = AsyncMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=None, response=response
            )
        return response
    return _mock_response


@pytest.mark.asyncio
async def test_health_check_success(bridge, mock_response):
    """Test successful health check."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(
            {"status": "healthy", "version": "1.0.0"}
        )
        
        result = await bridge.health_check()
        
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        mock_get.assert_called_once_with("/health")


@pytest.mark.asyncio
async def test_health_check_connection_error(bridge):
    """Test health check with connection error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.side_effect = httpx.RequestError("Connection failed")
        
        with pytest.raises(ConnectionError) as exc_info:
            await bridge.health_check()
        
        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_session_success(bridge, mock_response):
    """Test successful session creation."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response({
            "session_id": "test-session",
            "status": "qr_pending",
            "phone_number": None,
            "connected_at": None,
        })
        
        status = await bridge.create_session("test-session")
        
        assert isinstance(status, SessionStatus)
        assert status.session_id == "test-session"
        assert status.status == "qr_pending"
        mock_post.assert_called_once_with(
            "/sessions",
            json={
                "session_id": "test-session",
                "webhook_url": "http://localhost:8001/webhooks/whatsapp",
            }
        )


@pytest.mark.asyncio
async def test_create_session_already_exists(bridge, mock_response):
    """Test creating session that already exists."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response(status_code=409)
        
        with pytest.raises(SessionError) as exc_info:
            await bridge.create_session("test-session")
        
        assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_qr_code_success(bridge, mock_response):
    """Test successful QR code retrieval."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response({
            "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANS...",
            "timeout": 60,
        })
        
        qr_response = await bridge.get_qr_code("test-session")
        
        assert isinstance(qr_response, QRCodeResponse)
        assert qr_response.qr_code.startswith("data:image/png;base64,")
        assert qr_response.timeout == 60
        mock_get.assert_called_once_with("/sessions/test-session/qr")


@pytest.mark.asyncio
async def test_get_qr_code_session_not_found(bridge, mock_response):
    """Test getting QR code for non-existent session."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(status_code=404)
        
        with pytest.raises(SessionError) as exc_info:
            await bridge.get_qr_code("non-existent")
        
        assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_message_success(bridge, mock_response):
    """Test successful message sending."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response({
            "message_id": "msg-123",
            "timestamp": "2024-01-20T10:30:00Z",
            "status": "sent",
        })
        
        response = await bridge.send_message(
            session_id="test-session",
            recipient="+1234567890",
            content="Hello, World!",
        )
        
        assert isinstance(response, SendMessageResponse)
        assert response.message_id == "msg-123"
        assert response.status == "sent"
        
        # Check that phone number was formatted correctly
        call_args = mock_post.call_args[1]["json"]
        assert call_args["recipient_jid"] == "+1234567890@s.whatsapp.net"


@pytest.mark.asyncio
async def test_send_message_with_quote(bridge, mock_response):
    """Test sending message with quoted reply."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response({
            "message_id": "msg-124",
            "timestamp": "2024-01-20T10:31:00Z",
            "status": "sent",
        })
        
        response = await bridge.send_message(
            session_id="test-session",
            recipient="+1234567890",
            content="This is a reply",
            quoted_message_id="msg-123",
        )
        
        assert response.message_id == "msg-124"
        
        # Check quoted message was included
        call_args = mock_post.call_args[1]["json"]
        assert call_args["quoted_message_id"] == "msg-123"


@pytest.mark.asyncio
async def test_send_message_session_not_connected(bridge, mock_response):
    """Test sending message when session not connected."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response(status_code=400)
        
        with pytest.raises(SessionError) as exc_info:
            await bridge.send_message(
                session_id="test-session",
                recipient="+1234567890",
                content="Hello",
            )
        
        assert "not connected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_session_success(bridge, mock_response):
    """Test successful session deletion."""
    with patch.object(bridge.client, "delete") as mock_delete:
        mock_delete.return_value = mock_response(status_code=204)
        
        result = await bridge.delete_session("test-session")
        
        assert result is True
        mock_delete.assert_called_once_with("/sessions/test-session")


@pytest.mark.asyncio
async def test_delete_session_not_found(bridge, mock_response):
    """Test deleting non-existent session."""
    with patch.object(bridge.client, "delete") as mock_delete:
        mock_delete.return_value = mock_response(status_code=404)
        
        result = await bridge.delete_session("non-existent")
        
        assert result is False


@pytest.mark.asyncio
async def test_list_sessions_success(bridge, mock_response):
    """Test listing all sessions."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response([
            {
                "session_id": "session1",
                "status": "connected",
                "phone_number": "+1234567890",
                "connected_at": "2024-01-20T10:00:00Z",
            },
            {
                "session_id": "session2",
                "status": "qr_pending",
                "phone_number": None,
                "connected_at": None,
            },
        ])
        
        sessions = await bridge.list_sessions()
        
        assert len(sessions) == 2
        assert all(isinstance(s, SessionStatus) for s in sessions)
        assert sessions[0].session_id == "session1"
        assert sessions[0].status == "connected"
        assert sessions[1].session_id == "session2"
        assert sessions[1].status == "qr_pending"


@pytest.mark.asyncio
async def test_context_manager_without_enter():
    """Test that bridge requires context manager."""
    bridge = WhatsAppBridge(base_url="http://localhost:3000")
    
    with pytest.raises(RuntimeError) as exc_info:
        _ = bridge.client
    
    assert "context manager" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recipient_formatting():
    """Test that recipient phone numbers are formatted correctly."""
    async with WhatsAppBridge("http://localhost:3000") as bridge:
        with patch.object(bridge.client, "post") as mock_post:
            mock_post.return_value = AsyncMock(
                json=lambda: {"message_id": "123", "timestamp": "2024-01-20T10:00:00Z", "status": "sent"},
                status_code=200,
                raise_for_status=AsyncMock(),
            )
            
            # Test with plain number
            await bridge.send_message("session", "+1234567890", "test")
            call_args = mock_post.call_args[1]["json"]
            assert call_args["recipient_jid"] == "+1234567890@s.whatsapp.net"
            
            # Test with already formatted number
            await bridge.send_message("session", "+0987654321@s.whatsapp.net", "test")
            call_args = mock_post.call_args[1]["json"]
            assert call_args["recipient_jid"] == "+0987654321@s.whatsapp.net"
```

### services/private/tests/adapters/test_whatsapp_integration.py
```python
"""Integration tests for WhatsApp Bridge adapter."""
import pytest
import os
import asyncio
from datetime import datetime

from app.adapters.whatsapp import WhatsAppBridge, SessionError

# Skip integration tests by default
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_WHATSAPP", "false").lower() != "true",
    reason="WhatsApp integration tests disabled. Set INTEGRATION_TEST_WHATSAPP=true to run."
)


@pytest.fixture
async def bridge():
    """Create real WhatsApp Bridge connection."""
    # Use actual WhatsApp Bridge URL from environment or default
    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8001/webhooks/whatsapp")
    
    async with WhatsAppBridge(
        base_url=bridge_url,
        webhook_url=webhook_url,
        timeout=30.0,
    ) as bridge:
        yield bridge


@pytest.fixture
async def test_session_id():
    """Generate unique test session ID."""
    return f"test-session-{datetime.now().timestamp()}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_health_check(bridge):
    """Test health check against real WhatsApp Bridge."""
    health = await bridge.health_check()
    
    assert "status" in health
    assert health["status"] in ["healthy", "ok"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_session_lifecycle(bridge, test_session_id):
    """Test complete session lifecycle with real bridge."""
    # 1. Create session
    status = await bridge.create_session(test_session_id)
    assert status.session_id == test_session_id
    assert status.status == "qr_pending"
    
    try:
        # 2. Get QR code
        qr_response = await bridge.get_qr_code(test_session_id)
        assert qr_response.qr_code
        assert qr_response.qr_code.startswith("data:image/")
        
        # 3. Check session status
        status = await bridge.get_session_status(test_session_id)
        assert status.status == "qr_pending"
        
        # 4. List sessions (should include our test session)
        sessions = await bridge.list_sessions()
        session_ids = [s.session_id for s in sessions]
        assert test_session_id in session_ids
        
    finally:
        # 5. Clean up - delete session
        deleted = await bridge.delete_session(test_session_id)
        assert deleted is True
        
        # Verify deletion
        with pytest.raises(SessionError):
            await bridge.get_session_status(test_session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_duplicate_session(bridge, test_session_id):
    """Test creating duplicate session with real bridge."""
    # Create first session
    await bridge.create_session(test_session_id)
    
    try:
        # Try to create duplicate
        with pytest.raises(SessionError) as exc_info:
            await bridge.create_session(test_session_id)
        assert "already exists" in str(exc_info.value)
    finally:
        # Clean up
        await bridge.delete_session(test_session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_qr_code_timeout(bridge, test_session_id):
    """Test QR code has reasonable timeout."""
    await bridge.create_session(test_session_id)
    
    try:
        qr_response = await bridge.get_qr_code(test_session_id)
        
        # QR should have a timeout between 30-120 seconds typically
        assert 30 <= qr_response.timeout <= 120
    finally:
        await bridge.delete_session(test_session_id)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("WHATSAPP_TEST_CONNECTED_SESSION"),
    reason="No connected session available for testing. Set WHATSAPP_TEST_CONNECTED_SESSION"
)
async def test_real_send_message(bridge):
    """Test sending real message (requires connected session)."""
    session_id = os.getenv("WHATSAPP_TEST_CONNECTED_SESSION")
    recipient = os.getenv("WHATSAPP_TEST_RECIPIENT", "+1234567890")
    
    response = await bridge.send_message(
        session_id=session_id,
        recipient=recipient,
        content=f"Test message from Zapa integration test at {datetime.now()}",
    )
    
    assert response.message_id
    assert response.status == "sent"
    assert response.timestamp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_concurrent_operations(bridge):
    """Test concurrent operations don't interfere."""
    session_ids = [f"test-concurrent-{i}-{datetime.now().timestamp()}" for i in range(3)]
    
    try:
        # Create multiple sessions concurrently
        create_tasks = [bridge.create_session(sid) for sid in session_ids]
        statuses = await asyncio.gather(*create_tasks)
        
        assert len(statuses) == 3
        assert all(s.status == "qr_pending" for s in statuses)
        
        # Get QR codes concurrently
        qr_tasks = [bridge.get_qr_code(sid) for sid in session_ids]
        qr_responses = await asyncio.gather(*qr_tasks)
        
        assert len(qr_responses) == 3
        assert all(qr.qr_code for qr in qr_responses)
        
    finally:
        # Clean up all sessions
        delete_tasks = [bridge.delete_session(sid) for sid in session_ids]
        await asyncio.gather(*delete_tasks, return_exceptions=True)
```

### services/private/tests/adapters/conftest.py
```python
"""Fixtures for adapter tests."""
import pytest
import os


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


@pytest.fixture(autouse=True)
def integration_test_env(monkeypatch):
    """Auto-set integration test environment variables for tests."""
    # Ensure integration tests are off by default
    if "INTEGRATION_TEST_WHATSAPP" not in os.environ:
        monkeypatch.setenv("INTEGRATION_TEST_WHATSAPP", "false")
```

### Update pyproject.toml for integration tests

Add to `services/private/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_mode = "auto"
markers = [
    "integration: Integration tests that require external services",
]
env = [
    "ENVIRONMENT=test",
    "INTEGRATION_TEST_WHATSAPP=false",
    "INTEGRATION_TEST_OPENAI=false",
    "INTEGRATION_TEST_ANTHROPIC=false",
    "INTEGRATION_TEST_GOOGLE=false",
]
```

### Add integration test script

Create `scripts/test-integration.sh`:

```bash
#!/bin/bash
set -e

echo "🧪 Running integration tests..."
echo ""
echo "⚠️  WARNING: Integration tests require external services to be running!"
echo ""

# Check if WhatsApp Bridge is running
if [ "$1" == "whatsapp" ] || [ "$1" == "all" ]; then
    echo "Testing WhatsApp Bridge integration..."
    if ! curl -s http://localhost:3000/health > /dev/null; then
        echo "❌ WhatsApp Bridge not running on port 3000"
        echo "   Start it with: docker run -p 3000:3000 zapw/zapw"
        exit 1
    fi
    
    cd services/private
    INTEGRATION_TEST_WHATSAPP=true uv run pytest tests/adapters/test_whatsapp_integration.py -v -s
    cd ../..
fi

# Future: Add other integration tests (LLM providers, etc.)

echo ""
echo "✅ Integration tests completed!"
```

## Commands to Run

```bash
# Run unit tests only (default)
cd services/private
uv run pytest tests/adapters/test_whatsapp_unit.py -v

# Run integration tests (requires zapw running)
# First start zapw: docker run -p 3000:3000 zapw/zapw
INTEGRATION_TEST_WHATSAPP=true uv run pytest tests/adapters/test_whatsapp_integration.py -v -s

# Or use the script
chmod +x scripts/test-integration.sh
./scripts/test-integration.sh whatsapp

# Run all tests including integration
INTEGRATION_TEST_WHATSAPP=true uv run pytest tests/adapters/ -v

# Run with coverage
uv run pytest tests/adapters/test_whatsapp_unit.py -v --cov=app.adapters.whatsapp
```

## Verification

1. Unit tests pass without any external services
2. Integration tests are skipped by default
3. Integration tests pass when zapw is running and env var is set
4. Error handling works for all failure scenarios
5. Code coverage ≥ 90% from unit tests alone
6. CI/CD passes (integration tests skipped)

## Testing Notes

### Unit Tests
- Use mocks for all HTTP calls
- Test all error scenarios
- Test edge cases (formatting, retries, etc.)
- Should achieve >90% coverage

### Integration Tests  
- Skipped by default (environment variable)
- Test against real zapw instance
- Clean up all resources after tests
- Test concurrent operations
- Document required setup in comments

## Next Steps

After WhatsApp Bridge adapter is complete, proceed to Task 07: LLM Adapter Interface and Implementations.