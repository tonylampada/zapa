"""Redis configuration for the application."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class RedisSettings(BaseSettings):
    """Redis configuration settings."""

    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )
    redis_max_connections: int = Field(
        default=10,
        description="Maximum number of connections in the Redis pool",
    )
    redis_decode_responses: bool = Field(
        default=True,
        description="Whether to decode Redis responses to strings",
    )
    redis_socket_timeout: float = Field(
        default=5.0,
        description="Socket timeout for Redis operations in seconds",
    )
    redis_retry_on_timeout: bool = Field(
        default=True,
        description="Whether to retry operations on timeout",
    )

    # Message queue specific settings
    message_queue_prefix: str = Field(
        default="zapa:queue:",
        description="Prefix for message queue keys in Redis",
    )
    message_queue_ttl: int = Field(
        default=86400,  # 24 hours
        description="TTL for messages in the queue (seconds)",
    )
    message_queue_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed messages",
    )
    message_queue_retry_delay: int = Field(
        default=60,  # 1 minute
        description="Base delay between retries (seconds)",
    )

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global instance
redis_settings = RedisSettings()