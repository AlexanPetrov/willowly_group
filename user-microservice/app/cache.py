"""Redis cache management with connection pooling and graceful degradation."""

import json
from typing import Any, Optional
from redis import asyncio as aioredis
from app.config import settings
from app.logger import logger

# ==================== Cache Key Utilities ====================

USER_BY_ID_PREFIX = "user:id"
USER_BY_EMAIL_PREFIX = "user:email"


def make_cache_key(prefix: str, identifier: Any) -> str:
    """Generate consistent cache key with namespace.
    
    Args:
        prefix: Key prefix for namespacing (e.g., "user:id")
        identifier: Unique identifier (id, email, etc.)
        
    Returns:
        Formatted cache key (e.g., "user:id:123")
    """
    return f"{prefix}:{identifier}"

# ==================== Cache Manager ====================


class CacheManager:
    """Manages Redis connections and cache operations with graceful degradation.
    
    If Redis is unavailable, operations fail silently and return None/False,
    allowing the application to continue without caching.
    """
    
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Establish connection to Redis.
        
        Creates a connection pool and verifies connectivity with ping.
        Sets _redis to None if connection fails (graceful degradation).
        """
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
        """Close Redis connection.
        
        Properly closes the connection pool during application shutdown.
        """
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
        Delete all keys matching pattern using cursor-based iteration.
        
        Uses SCAN instead of KEYS to avoid blocking Redis in production.
        Deletes keys in batches for efficiency.
        
        Args:
            pattern: Redis pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self._redis:
            return 0
        
        try:
            keys_to_delete = []
            total_deleted = 0
            
            async for key in self._redis.scan_iter(match=pattern, count=100):
                keys_to_delete.append(key)
                
                # Batch delete every 100 keys
                if len(keys_to_delete) >= 100:
                    await self._redis.delete(*keys_to_delete)
                    total_deleted += len(keys_to_delete)
                    keys_to_delete.clear()
            
            # Delete remaining keys
            if keys_to_delete:
                await self._redis.delete(*keys_to_delete)
                total_deleted += len(keys_to_delete)
            
            if total_deleted > 0:
                logger.debug(f"[cache] DELETE PATTERN: {pattern} ({total_deleted} keys)")
            return total_deleted
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

# ==================== Global Instance ====================

cache_manager = CacheManager()
