"""WhatsApp Bridge adapter for zapw service."""

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

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
    phone_number: str | None = None
    connected_at: datetime | None = None
    error: str | None = None


class SendMessageRequest(BaseModel):
    """Request to send a message."""

    session_id: str
    recipient_jid: str
    content: str
    quoted_message_id: str | None = None


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
    content: str | None = None
    caption: str | None = None
    media_url: str | None = None
    quoted_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WhatsAppBridge:
    """Adapter for zapw WhatsApp Bridge service."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        webhook_url: str | None = None,
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
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WhatsAppBridge":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if not self._client:
            raise RuntimeError("WhatsAppBridge must be used as async context manager")
        return self._client

    async def health_check(self) -> dict[str, Any]:
        """Check if WhatsApp Bridge is healthy."""
        try:
            response = await self.client.get("/health")
            response.raise_for_status()
            return dict(response.json())
        except httpx.RequestError as e:
            logger.error(f"Health check failed: {e}")
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

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
                raise SessionError(f"Session {session_id} already exists") from e
            raise SessionError(f"Failed to create session: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

    async def get_session_status(self, session_id: str) -> SessionStatus:
        """Get status of a WhatsApp session."""
        try:
            response = await self.client.get(f"/sessions/{session_id}")
            response.raise_for_status()
            return SessionStatus(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SessionError(f"Session {session_id} not found") from e
            raise SessionError(f"Failed to get session status: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

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
                raise SessionError(f"Session {session_id} not found") from e
            if e.response.status_code == 400:
                raise SessionError("Session already connected") from e
            raise SessionError(f"Failed to get QR code: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

    async def send_message(
        self,
        session_id: str,
        recipient: str,
        content: str,
        quoted_message_id: str | None = None,
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
                raise SessionError(f"Session {session_id} not found") from e
            if e.response.status_code == 400:
                raise SessionError("Session not connected") from e
            raise WhatsAppBridgeError(f"Failed to send message: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

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
            raise SessionError(f"Failed to delete session: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e

    async def list_sessions(self) -> list[SessionStatus]:
        """List all active sessions."""
        try:
            response = await self.client.get("/sessions")
            response.raise_for_status()
            sessions_data = response.json()
            return [SessionStatus(**session) for session in sessions_data]
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to WhatsApp Bridge: {e}") from e
