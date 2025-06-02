"""Database utilities for dependency injection."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.config.database import DatabaseConfig
from app.core.config import settings

# Create database configuration
db_config = DatabaseConfig(
    DATABASE_URL=getattr(
        settings, "DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/whatsapp_agent"
    )
)

# Create session maker
SessionLocal = db_config.get_session_maker()


def get_db() -> Generator[Session, None, None]:
    """Get database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
