"""Retry logic with exponential backoff for I/O operations."""

import asyncio
import functools
import random
from typing import Any, Callable, TypeVar, cast

from app.logger import logger


F = TypeVar("F", bound=Callable[..., Any])


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async functions with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of attempts (including initial)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Add random jitter to delay
        exceptions: Tuple of exceptions to catch and retry on
    
    Example:
        @async_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            exc_info=True
                        )
                        raise
                    
                    # Calculate exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            
            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} exhausted retries")
        
        return cast(F, wrapper)
    
    return decorator


def sync_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for sync functions with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of attempts (including initial)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Add random jitter to delay
        exceptions: Tuple of exceptions to catch and retry on
    
    Example:
        @sync_retry(max_attempts=3, base_delay=1.0)
        def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            exc_info=True
                        )
                        raise
                    
                    # Calculate exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    import time
                    time.sleep(delay)
            
            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} exhausted retries")
        
        return cast(F, wrapper)
    
    return decorator
