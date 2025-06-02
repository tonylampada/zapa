"""Unit tests for WhatsApp Bridge adapter with mocked responses."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
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
        webhook_url="http://localhost:8001/api/v1/webhooks/whatsapp",
    ) as bridge:
        yield bridge


@pytest.fixture
def mock_response():
    """Create a mock response."""
    from unittest.mock import Mock

    def _mock_response(json_data=None, status_code=200):
        response = AsyncMock()
        # json() should be a sync method that returns data
        response.json = lambda: json_data or {}
        response.status_code = status_code

        # Create a real httpx.Response for error cases
        if status_code >= 400:
            # The HTTPStatusError expects response to have status_code
            error_response = Mock()
            error_response.status_code = status_code

            # raise_for_status is a sync method, not async
            response.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError(
                    f"HTTP {status_code}", request=Mock(), response=error_response
                )
            )
        else:
            # raise_for_status is a sync method
            response.raise_for_status = Mock()

        return response

    return _mock_response


@pytest.mark.asyncio
async def test_health_check_success(bridge, mock_response):
    """Test successful health check."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response({"status": "healthy", "version": "1.0.0"})

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
        mock_post.return_value = mock_response(
            {
                "session_id": "test-session",
                "status": "qr_pending",
                "phone_number": None,
                "connected_at": None,
            }
        )

        status = await bridge.create_session("test-session")

        assert isinstance(status, SessionStatus)
        assert status.session_id == "test-session"
        assert status.status == "qr_pending"
        mock_post.assert_called_once_with(
            "/sessions",
            json={
                "session_id": "test-session",
                "webhook_url": "http://localhost:8001/api/v1/webhooks/whatsapp",
            },
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
        mock_get.return_value = mock_response(
            {
                "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANS...",
                "timeout": 60,
            }
        )

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
        mock_post.return_value = mock_response(
            {
                "message_id": "msg-123",
                "timestamp": "2024-01-20T10:30:00Z",
                "status": "sent",
            }
        )

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
        mock_post.return_value = mock_response(
            {
                "message_id": "msg-124",
                "timestamp": "2024-01-20T10:31:00Z",
                "status": "sent",
            }
        )

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
        mock_delete.return_value = mock_response(status_code=200)

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
        mock_delete.assert_called_once_with("/sessions/non-existent")


@pytest.mark.asyncio
async def test_list_sessions_success(bridge, mock_response):
    """Test listing all sessions."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(
            [
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
            ]
        )

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
async def test_create_session_other_error(bridge, mock_response):
    """Test creating session with other HTTP error."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response(status_code=500)

        with pytest.raises(SessionError) as exc_info:
            await bridge.create_session("test-session")

        assert "Failed to create session" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_session_request_error(bridge):
    """Test creating session with connection error."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.create_session("test-session")

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_session_status_success(bridge, mock_response):
    """Test getting session status successfully."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(
            {
                "session_id": "test-session",
                "status": "connected",
                "phone_number": "+1234567890",
                "connected_at": "2024-01-20T10:00:00Z",
            }
        )

        status = await bridge.get_session_status("test-session")

        assert status.session_id == "test-session"
        assert status.status == "connected"
        assert status.phone_number == "+1234567890"


@pytest.mark.asyncio
async def test_get_session_status_not_found(bridge, mock_response):
    """Test getting non-existent session status."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(status_code=404)

        with pytest.raises(SessionError) as exc_info:
            await bridge.get_session_status("non-existent")

        assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_session_status_other_error(bridge, mock_response):
    """Test getting session status with other HTTP error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(status_code=500)

        with pytest.raises(SessionError) as exc_info:
            await bridge.get_session_status("test-session")

        assert "Failed to get session status" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_session_status_request_error(bridge):
    """Test getting session status with connection error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.get_session_status("test-session")

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_qr_code_already_connected(bridge, mock_response):
    """Test getting QR code when session already connected."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(status_code=400)

        with pytest.raises(SessionError) as exc_info:
            await bridge.get_qr_code("test-session")

        assert "already connected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_qr_code_other_error(bridge, mock_response):
    """Test getting QR code with other HTTP error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.return_value = mock_response(status_code=500)

        with pytest.raises(SessionError) as exc_info:
            await bridge.get_qr_code("test-session")

        assert "Failed to get QR code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_qr_code_request_error(bridge):
    """Test getting QR code with connection error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.get_qr_code("test-session")

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_message_not_found(bridge, mock_response):
    """Test sending message when session not found."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response(status_code=404)

        with pytest.raises(SessionError) as exc_info:
            await bridge.send_message("test-session", "+1234567890", "Hello")

        assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_message_other_error(bridge, mock_response):
    """Test sending message with other HTTP error."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.return_value = mock_response(status_code=500)

        with pytest.raises(WhatsAppBridgeError) as exc_info:
            await bridge.send_message("test-session", "+1234567890", "Hello")

        assert "Failed to send message" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_message_request_error(bridge):
    """Test sending message with connection error."""
    with patch.object(bridge.client, "post") as mock_post:
        mock_post.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.send_message("test-session", "+1234567890", "Hello")

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_session_other_error(bridge, mock_response):
    """Test deleting session with other HTTP error."""
    with patch.object(bridge.client, "delete") as mock_delete:
        mock_delete.return_value = mock_response(status_code=500)

        with pytest.raises(SessionError) as exc_info:
            await bridge.delete_session("test-session")

        assert "Failed to delete session" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_session_request_error(bridge):
    """Test deleting session with connection error."""
    with patch.object(bridge.client, "delete") as mock_delete:
        mock_delete.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.delete_session("test-session")

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_sessions_request_error(bridge):
    """Test listing sessions with connection error."""
    with patch.object(bridge.client, "get") as mock_get:
        mock_get.side_effect = httpx.RequestError("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await bridge.list_sessions()

        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_recipient_formatting():
    """Test that recipient phone numbers are formatted correctly."""
    async with WhatsAppBridge("http://localhost:3000") as bridge:
        with patch.object(bridge.client, "post") as mock_post:
            mock_post.return_value = AsyncMock(
                json=lambda: {
                    "message_id": "123",
                    "timestamp": "2024-01-20T10:00:00Z",
                    "status": "sent",
                },
                status_code=200,
                raise_for_status=Mock(),  # raise_for_status is sync
            )

            # Test with plain number
            await bridge.send_message("session", "+1234567890", "test")
            call_args = mock_post.call_args[1]["json"]
            assert call_args["recipient_jid"] == "+1234567890@s.whatsapp.net"

            # Test with already formatted number
            await bridge.send_message("session", "+0987654321@s.whatsapp.net", "test")
            call_args = mock_post.call_args[1]["json"]
            assert call_args["recipient_jid"] == "+0987654321@s.whatsapp.net"
