from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings shared between private and public services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Zapa"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3100", "http://localhost:3000"]

    # Security
    SECRET_KEY: str = "development-secret-key-change-in-production"
    ADMIN_TOKEN_SECRET: str = "admin-secret-change-in-production"
    ENCRYPTION_KEY: str = "development-encryption-key-change-in-production"

    # External Services
    WHATSAPP_BRIDGE_URL: str = "http://localhost:3000"
    DATABASE_URL: str = "postgresql://zapa:zapa@localhost:5432/zapa"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Integration Tests
    INTEGRATION_TEST_WHATSAPP: bool = False
    INTEGRATION_TEST_OPENAI: bool = False
    INTEGRATION_TEST_ANTHROPIC: bool = False
    INTEGRATION_TEST_GOOGLE: bool = False


settings = Settings()
