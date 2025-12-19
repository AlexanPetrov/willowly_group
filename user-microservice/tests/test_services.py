"""
Unit tests for business logic (services layer).
Tests service functions with mocked database calls.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from datetime import datetime, UTC
from app.services import (
    get_user,
    delete_user,
    list_users,
    search_users,
    batch_create_users,
    batch_delete_users,
)
from app.schemas import BatchCreateRequest, BatchDeleteRequest
from app.models import User
from app.cache import cache_manager, make_cache_key, USER_BY_ID_PREFIX, USER_BY_EMAIL_PREFIX
from app.config import settings


class MockUser:
    """Mock User object for testing with all required fields."""
    def __init__(self, id: int, name: str, email: str, is_active: bool = True):
        self.id = id
        self.name = name
        self.email = email
        self.hashed_password = "mock_hashed_password"
        self.is_active = is_active
        self.created_at = datetime.now(UTC)


def create_mock_user(id: int, name: str, email: str, is_active: bool = True):
    """Create a mock User object with all required fields."""
    return MockUser(id, name, email, is_active)


@pytest.mark.asyncio
class TestGetUser:
    """Test get_user service function."""
    
    async def test_get_user_success(self):
        """Test successful user retrieval."""
        # Clear cache before test to avoid pollution from other tests
        if settings.CACHE_ENABLED:
            await cache_manager.delete(make_cache_key(USER_BY_ID_PREFIX, 1))
        
        mock_user = create_mock_user(1, "Test User", "test@example.com")
        
        with patch('app.services.select_user', new_callable=AsyncMock, return_value=mock_user):
            result = await get_user(1)
            
            assert result.id == 1
            assert result.name == "Test User"
            assert result.email == "test@example.com"
    
    async def test_get_user_not_found(self):
        """Test that non-existent user raises HTTP 404."""
        with patch('app.services.select_user', new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_user(999)
            
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail["error"] == "USER_NOT_FOUND"
            assert "does not exist" in exc_info.value.detail["message"]


@pytest.mark.asyncio
class TestDeleteUser:
    """Test delete_user service function."""
    
    async def test_delete_user_success(self):
        """Test successful user deletion."""
        mock_user = create_mock_user(1, "Test User", "test@example.com")
        
        with patch('app.services.crud_delete_user', new_callable=AsyncMock, return_value=mock_user):
            result = await delete_user(1)
            
            assert result.id == 1
            assert result.name == "Test User"
            assert result.email == "test@example.com"
    
    async def test_delete_user_not_found(self):
        """Test that deleting non-existent user raises HTTP 404."""
        with patch('app.services.crud_delete_user', new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await delete_user(999)
            
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail["error"] == "USER_NOT_FOUND"
            assert "does not exist" in exc_info.value.detail["message"]


@pytest.mark.asyncio
class TestListUsers:
    """Test list_users service function."""
    
    async def test_list_users_success(self):
        """Test successful user listing with pagination."""
        mock_users = [
            create_mock_user(1, "User 1", "user1@example.com"),
            create_mock_user(2, "User 2", "user2@example.com"),
        ]
        
        with patch('app.services.crud_list_users', new_callable=AsyncMock, return_value=(mock_users, 2)):
            result = await list_users(page=1, limit=10)
            
            assert result.total == 2
            assert result.page == 1
            assert result.limit == 10
            assert result.pages == 1
            assert len(result.items) == 2
            assert result.items[0].id == 1
            assert result.items[1].id == 2
    
    async def test_list_users_pagination_calculation(self):
        """Test pagination calculation with multiple pages."""
        mock_users = [create_mock_user(i, f"User {i}", f"user{i}@example.com") for i in range(1, 6)]
        
        with patch('app.services.crud_list_users', new_callable=AsyncMock, return_value=(mock_users, 25)):
            result = await list_users(page=2, limit=5)
            
            assert result.total == 25
            assert result.page == 2
            assert result.limit == 5
            assert result.pages == 5  # 25 total / 5 per page = 5 pages
    
    async def test_list_users_empty(self):
        """Test listing when no users exist."""
        with patch('app.services.crud_list_users', new_callable=AsyncMock, return_value=([], 0)):
            result = await list_users(page=1, limit=10)
            
            assert result.total == 0
            assert result.pages == 0
            assert len(result.items) == 0
    
    async def test_list_users_with_filters(self):
        """Test listing with email filters."""
        mock_users = [create_mock_user(1, "User 1", "user1@example.com")]
        
        with patch('app.services.crud_list_users', new_callable=AsyncMock, return_value=(mock_users, 1)):
            result = await list_users(email="user1@example.com", page=1, limit=10)
            
            assert result.total == 1
            assert len(result.items) == 1
            assert result.items[0].email == "user1@example.com"
    
    async def test_list_users_limit_clamping(self):
        """Test that limit is clamped to MAX_LIMIT."""
        mock_users = []
        
        with patch('app.services.crud_list_users', new_callable=AsyncMock, return_value=(mock_users, 0)):
            result = await list_users(page=1, limit=1000)  # Over MAX_LIMIT (100)
            
            assert result.limit == 100  # Should be clamped to MAX_LIMIT


@pytest.mark.asyncio
class TestSearchUsers:
    """Test search_users service function."""
    
    async def test_search_users_success(self):
        """Test successful user search."""
        mock_users = [create_mock_user(1, "Alice", "alice@example.com")]
        
        with patch('app.services.crud_search_users', new_callable=AsyncMock, return_value=(mock_users, 1)):
            result = await search_users(q="alice", page=1, limit=10)
            
            assert result.total == 1
            assert len(result.items) == 1
            assert result.items[0].name == "Alice"
    
    async def test_search_users_no_results(self):
        """Test search with no matching results."""
        with patch('app.services.crud_search_users', new_callable=AsyncMock, return_value=([], 0)):
            result = await search_users(q="nonexistent", page=1, limit=10)
            
            assert result.total == 0
            assert len(result.items) == 0


@pytest.mark.asyncio
class TestBatchCreateUsers:
    """Test batch_create_users service function."""
    
    async def test_batch_create_success(self):
        """Test successful batch user creation."""
        mock_users = [
            create_mock_user(1, "User 1", "user1@example.com"),
            create_mock_user(2, "User 2", "user2@example.com"),
        ]
        
        with patch('app.services.crud_insert_users', new_callable=AsyncMock, return_value=mock_users):
            request = BatchCreateRequest(items=[
                {"name": "User 1", "email": "user1@example.com", "password": "password123"},
                {"name": "User 2", "email": "user2@example.com", "password": "password123"},
            ])
            result = await batch_create_users(request)
            
            assert result.created == 2
            assert len(result.items) == 2
            assert result.items[0].id == 1
            assert result.items[1].id == 2
    
    async def test_batch_create_exceeds_max_size(self):
        """Test that exceeding MAX_BATCH_SIZE raises HTTP 400."""
        items = [{"name": f"User {i}", "email": f"user{i}@example.com", "password": "password123"} for i in range(1001)]
        request = BatchCreateRequest(items=items)
        
        with pytest.raises(HTTPException) as exc_info:
            await batch_create_users(request)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "BATCH_SIZE_EXCEEDED"
        assert "exceeds maximum" in exc_info.value.detail["message"]
    
    async def test_batch_create_empty_list(self):
        """Test batch creation with empty list."""
        with patch('app.services.crud_insert_users', new_callable=AsyncMock, return_value=[]):
            request = BatchCreateRequest(items=[])
            result = await batch_create_users(request)
            
            assert result.created == 0
            assert len(result.items) == 0


@pytest.mark.asyncio
class TestBatchDeleteUsers:
    """Test batch_delete_users service function."""
    
    async def test_batch_delete_success(self):
        """Test successful batch user deletion."""
        mock_users = [
            create_mock_user(1, "User 1", "user1@example.com"),
            create_mock_user(2, "User 2", "user2@example.com"),
        ]
        
        with patch('app.services.crud_delete_users', new_callable=AsyncMock, return_value=mock_users):
            request = BatchDeleteRequest(ids=[1, 2])
            result = await batch_delete_users(request)
            
            assert result.deleted == 2
            assert len(result.items) == 2
            assert result.items[0].id == 1
            assert result.items[1].id == 2
    
    async def test_batch_delete_exceeds_max_size(self):
        """Test that exceeding MAX_BATCH_SIZE raises HTTP 400."""
        request = BatchDeleteRequest(ids=list(range(1, 1002)))
        
        with pytest.raises(HTTPException) as exc_info:
            await batch_delete_users(request)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "BATCH_SIZE_EXCEEDED"
        assert "exceeds maximum" in exc_info.value.detail["message"]
    
    async def test_batch_delete_empty_list(self):
        """Test batch deletion with empty list."""
        with patch('app.services.crud_delete_users', new_callable=AsyncMock, return_value=[]):
            request = BatchDeleteRequest(ids=[])
            result = await batch_delete_users(request)
            
            assert result.deleted == 0
            assert len(result.items) == 0
    
    async def test_batch_delete_partial_success(self):
        """Test batch deletion where some IDs don't exist."""
        mock_users = [create_mock_user(1, "User 1", "user1@example.com")]
        
        with patch('app.services.crud_delete_users', new_callable=AsyncMock, return_value=mock_users):
            request = BatchDeleteRequest(ids=[1, 999])  # 999 doesn't exist
            result = await batch_delete_users(request)
            
            assert result.deleted == 1
            assert len(result.items) == 1
            assert result.items[0].id == 1
