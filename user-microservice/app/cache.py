"""
Redis cache management for the User Microservice.
Provides connection management and cache utilities.
"""

import json
from typing import Any, Optional
from redis import asyncio as aioredis
from app.config import settings
from app.logger import logger


class CacheManager:
    """Manages Redis connections and cache operations."""
    
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Establish connection to Redis."""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                await self._redis.ping()
                logger.info("[cache] Connected to Redis")
            except Exception as e:
                logger.error(f"[cache] Failed to connect to Redis: {e}")
                self._redis = None
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("[cache] Disconnected from Redis")
    
    async def get(self, key: str) -> Optional[dict]:
        """
        Get value from cache by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value as dict, or None if not found
        """
        if not self._redis:
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                logger.debug(f"[cache] HIT: {key}")
                return json.loads(value)
            logger.debug(f"[cache] MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"[cache] Error getting key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = use default)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._redis:
            return False
        
        try:
            ttl = ttl or settings.CACHE_TTL
            serialized = json.dumps(value, default=str)
            await self._redis.setex(key, ttl, serialized)
            logger.debug(f"[cache] SET: {key} (TTL={ttl}s)")
            return True
        except Exception as e:
            logger.error(f"[cache] Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            logger.debug(f"[cache] DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"[cache] Error deleting key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Redis pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self._redis:
            return 0
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                deleted = await self._redis.delete(*keys)
                logger.debug(f"[cache] DELETE PATTERN: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"[cache] Error deleting pattern {pattern}: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """
        Check if Redis is healthy.
        
        Returns:
            True if Redis responds to ping, False otherwise
        """
        if not self._redis:
            return False
        
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


# Global cache manager instance
cache_manager = CacheManager()


def make_cache_key(prefix: str, identifier: Any) -> str:
    """
    Generate consistent cache key.
    
    Args:
        prefix: Key prefix (e.g., "user")
        identifier: Unique identifier (id, email, etc.)
        
    Returns:
        Cache key string
    """
    return f"{prefix}:{identifier}"


# Cache key prefixes
USER_BY_ID_PREFIX = "user:id"
USER_BY_EMAIL_PREFIX = "user:email"

