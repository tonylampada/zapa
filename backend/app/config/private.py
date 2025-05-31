"""Private entrypoint configuration."""
from pydantic import Field

from app.config import DatabaseConfig


class PrivateSettings(DatabaseConfig):
    """Configuration for Zapa Private entrypoint."""

    # Service Info
    SERVICE_NAME: str = Field(default="zapa-private")
    VERSION: str = Field(default="0.1.0")

    # External Services
    WHATSAPP_BRIDGE_URL: str = Field(
        default="http://localhost:3000",
        description="WhatsApp Bridge (zapw) service URL",
    )
    WHATSAPP_BRIDGE_TIMEOUT: float = Field(
        default=30.0, ge=5.0, le=300.0, description="WhatsApp Bridge timeout"
    )
    
    # WhatsApp Configuration
    WHATSAPP_SYSTEM_NUMBER: str = Field(
        default="+1234567890",
        description="Main WhatsApp service number that receives user messages",
    )

    # Webhook
    WEBHOOK_BASE_URL: str = Field(
        default="http://localhost:8001",
        description="Base URL for webhooks from external services",
    )

    # Admin Authentication
    ADMIN_TOKEN_SECRET: str = Field(
        ..., min_length=32, description="Admin JWT token secret"
    )
    ADMIN_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24, ge=30, description="Admin token expiry in minutes"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, ge=1)

    # Integration Tests
    INTEGRATION_TEST_WHATSAPP: bool = Field(default=False)
    INTEGRATION_TEST_OPENAI: bool = Field(default=False)
    INTEGRATION_TEST_ANTHROPIC: bool = Field(default=False)
    INTEGRATION_TEST_GOOGLE: bool = Field(default=False)

    @property
    def webhook_url(self) -> str:
        """Get full webhook URL."""
        return f"{self.WEBHOOK_BASE_URL.rstrip('/')}/api/v1/webhooks/whatsapp"


# Global settings instance
# This will be initialized when the module is imported in production
# For tests, create instances with explicit values
try:
    settings = PrivateSettings()  # type: ignore[call-arg]
except Exception:
    # Settings will be created in tests with required values
    settings = None  # type: ignore
