"""
Database connection and session management for MCP Character Service.
"""
import os
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
import structlog

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized = False
    
    async def initialize(self, database_url: Optional[str] = None) -> None:
        """Initialize database connection."""
        if self._initialized:
            return
        
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://character_user:character_pass@localhost:5432/character_db"
            )
        
        logger.info("Initializing database connection", database_url=database_url.split('@')[0] + '@***')
        
        # Configure engine based on environment
        engine_kwargs = {
            "echo": os.getenv("DEBUG", "false").lower() == "true",
            "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
            "pool_recycle": 3600,  # Recycle connections every hour
        }
        
        # Special handling for test database (in-memory SQLite)
        if "sqlite" in database_url:
            engine_kwargs.update({
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
                "pool_size": 1,
                "max_overflow": 0,
            })
        
        self._engine = create_async_engine(database_url, **engine_kwargs)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info("Database connection initialized successfully")
    
    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        if not self._initialized:
            await self.initialize()
        
        if not self._session_factory:
            raise RuntimeError("Database not initialized")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self._initialized:
            await self.initialize()
        
        if not self._engine:
            raise RuntimeError("Database not initialized")
        
        logger.info("Creating database tables")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    
    async def drop_tables(self) -> None:
        """Drop all database tables (for testing)."""
        if not self._initialized:
            await self.initialize()
        
        if not self._engine:
            raise RuntimeError("Database not initialized")
        
        logger.warning("Dropping all database tables")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            if not self._initialized:
                await self.initialize()
            
            async with self.get_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function to get database session."""
    async with db_manager.get_session() as session:
        yield session


async def initialize_database(database_url: Optional[str] = None) -> None:
    """Initialize database connection."""
    await db_manager.initialize(database_url)


async def create_database_tables() -> None:
    """Create all database tables."""
    await db_manager.create_tables()


async def close_database() -> None:
    """Close database connections."""
    await db_manager.close()


async def database_health_check() -> bool:
    """Check database health."""
    return await db_manager.health_check()


# Context manager for database lifecycle
@asynccontextmanager
async def database_lifespan(database_url: Optional[str] = None):
    """Context manager for database lifecycle management."""
    try:
        await initialize_database(database_url)
        await create_database_tables()
        yield
    finally:
        await close_database()


# Transaction management utilities
@asynccontextmanager
async def database_transaction(session: AsyncSession):
    """Context manager for explicit transaction management."""
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class ConnectionError(DatabaseError):
    """Database connection error."""
    pass


class TransactionError(DatabaseError):
    """Database transaction error."""
    pass
