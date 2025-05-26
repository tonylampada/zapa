"""Database connection utilities."""
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import DatabaseConfig
from models.base import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database manager.

        Args:
            config: Database configuration
        """
        self.config = config
        self._engine = None
        self._async_engine = None
        self._session_maker = None
        self._async_session_maker = None

    @property
    def engine(self):
        """Get synchronous SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.config.DATABASE_URL,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                echo=self.config.DATABASE_ECHO,
            )
        return self._engine

    @property
    def async_engine(self):
        """Get asynchronous SQLAlchemy engine."""
        if self._async_engine is None:
            # Convert postgresql:// to postgresql+asyncpg://
            async_url = self.config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            self._async_engine = create_async_engine(
                async_url,
                pool_size=self.config.DATABASE_POOL_SIZE,
                max_overflow=self.config.DATABASE_MAX_OVERFLOW,
                echo=self.config.DATABASE_ECHO,
            )
        return self._async_engine

    @property
    def session_maker(self):
        """Get synchronous session maker."""
        if self._session_maker is None:
            self._session_maker = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
            )
        return self._session_maker

    @property
    def async_session_maker(self):
        """Get asynchronous session maker."""
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_maker

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Created all database tables")

    def drop_tables(self):
        """Drop all tables."""
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Dropped all database tables")

    async def create_tables_async(self):
        """Create all tables asynchronously."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Created all database tables (async)")

    async def drop_tables_async(self):
        """Drop all tables asynchronously."""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Dropped all database tables (async)")

    def get_session(self) -> Session:
        """Get a synchronous database session."""
        return self.session_maker()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session."""
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self):
        """Close database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._engine:
            self._engine.dispose()


class TestDatabaseManager(DatabaseManager):
    """Database manager for testing with in-memory SQLite."""

    __test__ = False  # Tell pytest to skip this class

    def __init__(self):
        """Initialize test database manager."""
        # Use in-memory SQLite for tests
        self._test_engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self._test_session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._test_engine,
        )

    @property
    def engine(self):
        """Get test engine."""
        return self._test_engine

    @property
    def session_maker(self):
        """Get test session maker."""
        return self._test_session_maker

    def create_tables(self):
        """Create all tables in test database."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all tables in test database."""
        Base.metadata.drop_all(bind=self.engine)


# Global database manager instances
_db_manager: DatabaseManager | None = None


def get_database_manager(config: DatabaseConfig | None = None) -> DatabaseManager:
    """Get or create database manager instance."""
    global _db_manager
    if _db_manager is None:
        if config is None:
            from app.config.database import DatabaseConfig

            config = DatabaseConfig()
        _db_manager = DatabaseManager(config)
    return _db_manager


def get_db_session():
    """Dependency to get database session."""
    db_manager = get_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


async def get_async_db_session():
    """Dependency to get async database session."""
    db_manager = get_database_manager()
    async with db_manager.get_async_session() as session:
        yield session
