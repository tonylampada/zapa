"""Base configuration settings."""
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings


class BaseSettings(PydanticBaseSettings):
    """Base settings for backend application."""

    # Environment
    ENVIRONMENT: Literal["development", "test", "production"] = Field(
        default="development", description="Application environment"
    )
    DEBUG: bool = Field(default=True, description="Debug mode")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )

    # API Settings
    API_V1_STR: str = Field(default="/api/v1", description="API version prefix")
    PROJECT_NAME: str = Field(default="Zapa", description="Project name")

    # Security
    SECRET_KEY: str = Field(
        ..., min_length=32, description="Secret key for JWT signing"
    )
    ENCRYPTION_KEY: str = Field(
        ..., min_length=32, description="Key for encrypting user API keys"
    )

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3100",  # Private frontend
            "http://localhost:3200",  # Public frontend
        ]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("SECRET_KEY", "ENCRYPTION_KEY")
    @classmethod
    def validate_keys(cls, v):
        """Validate that keys are strong enough."""
        if len(v) < 32:
            raise ValueError("Key must be at least 32 characters long")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }
