"""Public entrypoint configuration."""

from pydantic import Field, field_validator

from app.config import DatabaseConfig


class PublicSettings(DatabaseConfig):
    """Configuration for Zapa Public entrypoint."""

    # Service Info
    SERVICE_NAME: str = Field(default="zapa-public")
    VERSION: str = Field(default="0.1.0")

    # Authentication
    AUTH_CODE_LENGTH: int = Field(default=6, ge=4, le=8)
    AUTH_CODE_EXPIRE_MINUTES: int = Field(default=5, ge=1, le=15)
    JWT_TOKEN_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1, le=90)

    # Rate Limiting
    AUTH_RATE_LIMIT_PER_HOUR: int = Field(default=10, ge=1, le=100)
    API_RATE_LIMIT_PER_MINUTE: int = Field(default=100, ge=1)

    # WhatsApp Service
    WHATSAPP_API_URL: str = Field(
        default="http://localhost:3000",
        description="URL of WhatsApp Bridge service",
    )
    WHATSAPP_API_KEY: str | None = Field(
        default=None,
        description="API key for WhatsApp Bridge (if required)",
    )

    # Private Service Communication
    PRIVATE_SERVICE_URL: str = Field(
        default="http://localhost:8001",
        description="URL of private service for internal communication",
    )
    PRIVATE_SERVICE_TIMEOUT: float = Field(default=10.0, ge=1.0, le=60.0)
    PRIVATE_SERVICE_SECRET: str = Field(
        default="shared-secret-for-dev-change-in-prod",
        min_length=32,
        description="Shared secret for service-to-service auth",
    )

    # Data Access
    MAX_MESSAGES_PER_REQUEST: int = Field(default=100, ge=1, le=1000)
    MAX_SEARCH_RESULTS: int = Field(default=50, ge=1, le=200)
    MESSAGE_HISTORY_DAYS: int = Field(default=365, ge=1)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def set_public_cors_origins(cls, v):
        """Set CORS origins for public service."""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(",")]
        else:
            origins = v or []

        # Add default public frontend URL if not present
        default_public = "http://localhost:3200"
        if default_public not in origins:
            origins.append(default_public)

        return origins


# Global settings instance
# This will be initialized when the module is imported in production
# For tests, create instances with explicit values
try:
    settings = PublicSettings()  # type: ignore[call-arg]
except Exception:
    # Settings will be created in tests with required values
    settings = None  # type: ignore
