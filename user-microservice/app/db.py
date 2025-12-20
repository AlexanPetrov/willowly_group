# DB connection & session management

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy import text
import asyncio
from .config import settings
from .logger import logger

# Async connection pool with production-ready configuration
engine = create_async_engine(
    settings.DB_URL,
    echo=False,
    future=True,
    pool_size=settings.DB_POOL_SIZE,  # Maintain 20 connections in pool
    max_overflow=settings.DB_MAX_OVERFLOW,  # Allow 10 extra connections during peaks
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Wait 30s for connection
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections every hour
    pool_pre_ping=True,  # Verify connections before using them
    connect_args={
        "timeout": settings.DB_CONNECT_TIMEOUT,  # Connection timeout (seconds)
        "command_timeout": settings.DB_QUERY_TIMEOUT,  # Query execution timeout (seconds)
    },
)

logger.info(
    f"Database engine configured: pool_size={settings.DB_POOL_SIZE}, "
    f"max_overflow={settings.DB_MAX_OVERFLOW}, timeout={settings.DB_POOL_TIMEOUT}s"
)

# Factory that gives AsyncSession objects
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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

# Class for all ORM models (models.py)
Base = declarative_base()

# Beforehand:
    # Create database (user_microservice_db) - done manually once
    # Start PostgreSQL server - via Homebrew
    
# NOTE: Schema is now managed by Alembic migrations (use `make migrate-up`)
# The init_models() function below is kept for reference but should NOT be used
# Uncomment only if you need to quickly recreate tables without migrations (not recommended)

# async def init_models():
#     """DEPRECATED: Use Alembic migrations instead. Kept for emergency use only."""
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    """Gracefully close all database connections."""
    logger.info("Disposing database engine and closing connections")
    try:
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error disposing database engine: {str(e)}", exc_info=True)
