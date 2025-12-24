"""Database connection pooling, session management, and resilience utilities."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy import text
import asyncio
from .config import settings
from .logger import logger

# ==================== Connection Pool Setup ====================

engine = create_async_engine(
    settings.DB_URL,
    echo=False,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before use
    connect_args={
        "timeout": settings.DB_CONNECT_TIMEOUT,
        "command_timeout": settings.DB_QUERY_TIMEOUT,
    },
)

logger.info(
    f"Database engine configured: pool_size={settings.DB_POOL_SIZE}, "
    f"max_overflow={settings.DB_MAX_OVERFLOW}, timeout={settings.DB_POOL_TIMEOUT}s"
)

# Session factory for creating database sessions
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Base class for ORM models
Base = declarative_base()

# ==================== Database Resilience ====================


async def retry_on_db_error(func, max_retries: int = 3, base_delay: float = 0.5):
    """Retry database operations with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        
    Returns:
        Result of the function call
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except (OperationalError, DBAPIError) as e:
            last_exception = e
            
            # Check if error is retryable (connection issues, not constraint violations)
            error_msg = str(e).lower()
            is_retryable = any([
                "connection" in error_msg,
                "timeout" in error_msg,
                "database is locked" in error_msg,
                "server closed the connection" in error_msg,
                "connection reset" in error_msg,
            ])
            
            if not is_retryable or attempt == max_retries - 1:
                logger.error(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries}): {str(e)}",
                    exc_info=True
                )
                raise
            
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            logger.warning(
                f"Database error on attempt {attempt + 1}/{max_retries}, "
                f"retrying in {delay}s: {str(e)}"
            )
            await asyncio.sleep(delay)
    
    raise last_exception


async def check_db_connection() -> bool:
    """Check if database connection is healthy.
    
    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        async def _check():
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
        
        await retry_on_db_error(_check, max_retries=2, base_delay=0.1)
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

# ==================== Cleanup ====================

async def dispose_engine():
    """Gracefully close all database connections.
    
    Called during application shutdown to properly cleanup connection pool.
    Ensures all connections are closed before application terminates.
    """
    logger.info("Disposing database engine and closing connections")
    try:
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error disposing database engine: {str(e)}", exc_info=True)
