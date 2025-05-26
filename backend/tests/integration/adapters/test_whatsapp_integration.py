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
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8001/api/v1/webhooks/whatsapp")
    
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