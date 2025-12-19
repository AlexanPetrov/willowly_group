"""
Tests for Redis cache functionality.
"""

import pytest
from app.cache import cache_manager, make_cache_key, USER_BY_ID_PREFIX, USER_BY_EMAIL_PREFIX
from app.services import get_user, register_user, delete_user
from app.schemas import UserRegister


@pytest.mark.asyncio
async def test_cache_pattern_delete(client):
    """Test deleting multiple keys by pattern."""
    # Set multiple test keys
    await cache_manager.set("test:user:1", {"id": 1}, ttl=60)
    await cache_manager.set("test:user:2", {"id": 2}, ttl=60)
    await cache_manager.set("test:user:3", {"id": 3}, ttl=60)
    await cache_manager.set("other:key", {"id": 99}, ttl=60)
    
    # Delete pattern
    deleted = await cache_manager.delete_pattern("test:user:*")
    assert deleted >= 3, f"Should delete at least 3 keys matching pattern, deleted {deleted}"
    
    # Verify pattern keys deleted
    assert await cache_manager.get("test:user:1") is None
    assert await cache_manager.get("test:user:2") is None
    assert await cache_manager.get("test:user:3") is None
    
    # Verify other key still exists
    assert await cache_manager.get("other:key") is not None
    
    # Cleanup
    await cache_manager.delete("other:key")


@pytest.mark.asyncio
async def test_get_user_cache_hit(client):
    """Test that get_user returns cached data on second call."""
    # Create a user
    user_data = UserRegister(
        name="Cache Test User",
        email="cachetest@example.com",
        password="password123"
    )
    created_user = await register_user(user_data)
    
    # First call - should cache the user
    user1 = await get_user(created_user.id)
    assert user1.id == created_user.id
    
    # Verify it's in cache
    cache_key = make_cache_key(USER_BY_ID_PREFIX, created_user.id)
    cached_data = await cache_manager.get(cache_key)
    assert cached_data is not None, "User should be cached after first get"
    assert cached_data["id"] == created_user.id
    
    # Second call - should hit cache
    user2 = await get_user(created_user.id)
    assert user2.id == created_user.id
    assert user2.email == user1.email


@pytest.mark.asyncio
async def test_delete_user_invalidates_cache(client):
    """Test that deleting a user invalidates both ID and email cache."""
    # Create a user
    user_data = UserRegister(
        name="Delete Cache Test",
        email="deletecache@example.com",
        password="password123"
    )
    created_user = await register_user(user_data)
    
    # Cache the user by calling get_user
    await get_user(created_user.id)
    
    # Verify it's cached
    id_cache_key = make_cache_key(USER_BY_ID_PREFIX, created_user.id)
    email_cache_key = make_cache_key(USER_BY_EMAIL_PREFIX, created_user.email)
    
    assert await cache_manager.get(id_cache_key) is not None, "User should be cached by ID"
    assert await cache_manager.get(email_cache_key) is not None, "User should be cached by email"
    
    # Delete the user
    await delete_user(created_user.id)
    
    # Verify cache is invalidated
    assert await cache_manager.get(id_cache_key) is None, "ID cache should be invalidated"
    assert await cache_manager.get(email_cache_key) is None, "Email cache should be invalidated"


@pytest.mark.asyncio
async def test_register_user_caches_data(client):
    """Test that registering a user stores it in cache."""
    user_data = UserRegister(
        name="Register Cache Test",
        email="registercache@example.com",
        password="password123"
    )
    
    created_user = await register_user(user_data)
    
    # Verify user is cached by ID
    id_cache_key = make_cache_key(USER_BY_ID_PREFIX, created_user.id)
    cached_by_id = await cache_manager.get(id_cache_key)
    assert cached_by_id is not None, "Newly registered user should be cached by ID"
    assert cached_by_id["id"] == created_user.id
    
    # Verify user is cached by email
    email_cache_key = make_cache_key(USER_BY_EMAIL_PREFIX, created_user.email)
    cached_by_email = await cache_manager.get(email_cache_key)
    assert cached_by_email is not None, "Newly registered user should be cached by email"
    assert cached_by_email["email"] == created_user.email


@pytest.mark.asyncio
async def test_health_check_includes_cache(client):
    """Test that /health endpoint includes cache status."""
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "cache" in data, "Health check should include cache status"
    # Just verify it has one of the expected statuses
    assert data["cache"] in ["connected", "disconnected", "disabled", "error"], \
        f"Cache status should be valid, got: {data['cache']}"


@pytest.mark.asyncio
async def test_make_cache_key():
    """Test cache key generation."""
    key1 = make_cache_key("user", 123)
    assert key1 == "user:123"
    
    key2 = make_cache_key("email", "test@example.com")
    assert key2 == "email:test@example.com"
    
    key3 = make_cache_key(USER_BY_ID_PREFIX, 456)
    assert key3.startswith("user:id:")

