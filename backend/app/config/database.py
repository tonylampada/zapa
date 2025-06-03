"""Database configuration."""

from pydantic import Field, field_validator
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from .base import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DATABASE_POOL_SIZE: int = Field(
        default=5, ge=1, le=20, description="Database connection pool size"
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10, ge=0, le=50, description="Database max overflow connections"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    REDIS_KEY_PREFIX: str = Field(default="zapa:", description="Redis key prefix")
    REDIS_SESSION_TTL: int = Field(default=3600, ge=300, description="Session TTL in seconds")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must be a Redis URL")
        return v

    def get_database_engine(self) -> Engine:
        """Create SQLAlchemy engine."""
        return create_engine(
            self.DATABASE_URL,
            pool_size=self.DATABASE_POOL_SIZE,
            max_overflow=self.DATABASE_MAX_OVERFLOW,
            echo=self.DATABASE_ECHO,
        )

    def get_session_maker(self) -> sessionmaker:
        """Create SQLAlchemy session maker."""
        engine = self.get_database_engine()
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
