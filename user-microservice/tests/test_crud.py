"""
Unit tests for database layer (CRUD operations).
Tests CRUD functions with real database using test fixtures.
"""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from app.crud import (
    insert_user,
    select_user,
    delete_user,
    list_users,
    search_users,
    insert_users,
    delete_users,
)
from app.models import User
from app.auth import hash_password

# Helper function for tests - provides a default hashed password
def get_test_password_hash() -> str:
    """Get a hashed password for test users."""
    return hash_password("test_password_123")


@pytest.mark.asyncio
class TestInsertUser:
    """Test insert_user CRUD function."""
    
    async def test_insert_user_success(self, test_db_engine):
        """Test successful user insertion."""
        user = await insert_user("Test User", "test@example.com", get_test_password_hash())
        
        assert user.id is not None
        assert user.name == "Test User"
        assert user.email == "test@example.com"
    
    async def test_insert_user_duplicate_email(self, test_db_engine):
        """Test that duplicate email raises ValueError."""
        await insert_user("User 1", "duplicate@example.com", get_test_password_hash())
        
        with pytest.raises(ValueError, match="duplicate email"):
            await insert_user("User 2", "duplicate@example.com", get_test_password_hash())


@pytest.mark.asyncio
class TestSelectUser:
    """Test select_user CRUD function."""
    
    async def test_select_user_success(self, test_db_engine):
        """Test successful user selection."""
        created_user = await insert_user("Test User", "test@example.com", get_test_password_hash())
        
        user = await select_user(created_user.id)
        
        assert user is not None
        assert user.id == created_user.id
        assert user.name == "Test User"
        assert user.email == "test@example.com"
    
    async def test_select_user_not_found(self, test_db_engine):
        """Test selecting non-existent user returns None."""
        user = await select_user(99999)
        assert user is None


@pytest.mark.asyncio
class TestDeleteUser:
    """Test delete_user CRUD function."""
    
    async def test_delete_user_success(self, test_db_engine):
        """Test successful user deletion."""
        created_user = await insert_user("Test User", "test@example.com", get_test_password_hash())
        
        deleted_user = await delete_user(created_user.id)
        
        assert deleted_user is not None
        assert deleted_user.id == created_user.id
        assert deleted_user.name == "Test User"
        assert deleted_user.email == "test@example.com"
        
        # Verify user is actually deleted
        user = await select_user(created_user.id)
        assert user is None
    
    async def test_delete_user_not_found(self, test_db_engine):
        """Test deleting non-existent user returns None."""
        deleted_user = await delete_user(99999)
        assert deleted_user is None


@pytest.mark.asyncio
class TestListUsers:
    """Test list_users CRUD function."""
    
    async def test_list_users_empty(self, test_db_engine):
        """Test listing users when database is empty."""
        users, total = await list_users(skip=0, limit=10)
        
        assert users == []
        assert total == 0
    
    async def test_list_users_basic_pagination(self, test_db_engine):
        """Test basic user listing with pagination."""
        # Create 5 users
        for i in range(1, 6):
            await insert_user(f"User {i}", f"user{i}@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10)
        
        assert len(users) == 5
        assert total == 5
    
    async def test_list_users_pagination_skip(self, test_db_engine):
        """Test pagination with skip offset."""
        # Create 5 users
        for i in range(1, 6):
            await insert_user(f"User {i}", f"user{i}@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=2, limit=2)
        
        assert len(users) == 2
        assert total == 5
    
    async def test_list_users_filter_by_email(self, test_db_engine):
        """Test filtering users by exact email."""
        await insert_user("User 1", "user1@example.com", get_test_password_hash())
        await insert_user("User 2", "user2@example.com", get_test_password_hash())
        await insert_user("User 3", "user3@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10, email="user2@example.com")
        
        assert len(users) == 1
        assert total == 1
        assert users[0].email == "user2@example.com"
    
    async def test_list_users_filter_by_domain(self, test_db_engine):
        """Test filtering users by email domain."""
        await insert_user("User 1", "user1@example.com", get_test_password_hash())
        await insert_user("User 2", "user2@test.com", get_test_password_hash())
        await insert_user("User 3", "user3@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10, email_domain="example.com")
        
        assert len(users) == 2
        assert total == 2
        assert all(user.email.endswith("@example.com") for user in users)
    
    async def test_list_users_sort_by_name_asc(self, test_db_engine):
        """Test sorting users by name ascending."""
        await insert_user("Charlie", "charlie@example.com", get_test_password_hash())
        await insert_user("Alice", "alice@example.com", get_test_password_hash())
        await insert_user("Bob", "bob@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10, sort="name", order="asc")
        
        assert len(users) == 3
        assert users[0].name == "Alice"
        assert users[1].name == "Bob"
        assert users[2].name == "Charlie"
    
    async def test_list_users_sort_by_name_desc(self, test_db_engine):
        """Test sorting users by name descending."""
        await insert_user("Charlie", "charlie@example.com", get_test_password_hash())
        await insert_user("Alice", "alice@example.com", get_test_password_hash())
        await insert_user("Bob", "bob@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10, sort="name", order="desc")
        
        assert len(users) == 3
        assert users[0].name == "Charlie"
        assert users[1].name == "Bob"
        assert users[2].name == "Alice"
    
    async def test_list_users_sort_by_email(self, test_db_engine):
        """Test sorting users by email."""
        await insert_user("User C", "c@example.com", get_test_password_hash())
        await insert_user("User A", "a@example.com", get_test_password_hash())
        await insert_user("User B", "b@example.com", get_test_password_hash())
        
        users, total = await list_users(skip=0, limit=10, sort="email", order="asc")
        
        assert len(users) == 3
        assert users[0].email == "a@example.com"
        assert users[1].email == "b@example.com"
        assert users[2].email == "c@example.com"


@pytest.mark.asyncio
class TestSearchUsers:
    """Test search_users CRUD function."""
    
    async def test_search_users_by_name(self, test_db_engine):
        """Test searching users by name."""
        await insert_user("Alice Smith", "alice@example.com", get_test_password_hash())
        await insert_user("Bob Johnson", "bob@example.com", get_test_password_hash())
        await insert_user("Alice Jones", "alicejon@example.com", get_test_password_hash())
        
        users, total = await search_users(query="Alice", skip=0, limit=10)
        
        assert len(users) == 2
        assert total == 2
        assert all("Alice" in user.name for user in users)
    
    async def test_search_users_by_email(self, test_db_engine):
        """Test searching users by email."""
        await insert_user("User 1", "alice@example.com", get_test_password_hash())
        await insert_user("User 2", "bob@test.com", get_test_password_hash())
        await insert_user("User 3", "alice@test.com", get_test_password_hash())
        
        users, total = await search_users(query="alice", skip=0, limit=10)
        
        assert len(users) == 2
        assert total == 2
        assert all("alice" in user.email for user in users)
    
    async def test_search_users_case_insensitive(self, test_db_engine):
        """Test that search is case-insensitive."""
        await insert_user("Alice", "alice@example.com", get_test_password_hash())
        
        users, total = await search_users(query="ALICE", skip=0, limit=10)
        
        assert len(users) == 1
        assert users[0].name == "Alice"
    
    async def test_search_users_partial_match(self, test_db_engine):
        """Test that search matches partial strings."""
        await insert_user("Alexander", "alex@example.com", get_test_password_hash())
        
        users, total = await search_users(query="Alex", skip=0, limit=10)
        
        assert len(users) == 1
        assert users[0].name == "Alexander"
    
    async def test_search_users_no_results(self, test_db_engine):
        """Test search with no matching results."""
        await insert_user("Alice", "alice@example.com", get_test_password_hash())
        
        users, total = await search_users(query="nonexistent", skip=0, limit=10)
        
        assert len(users) == 0
        assert total == 0
    
    async def test_search_users_special_characters(self, test_db_engine):
        """Test search properly escapes special SQL characters."""
        await insert_user("User_100%", "special@example.com", get_test_password_hash())
        
        users, total = await search_users(query="100%", skip=0, limit=10)
        
        assert len(users) == 1
        assert users[0].name == "User_100%"
    
    async def test_search_users_with_pagination(self, test_db_engine):
        """Test search with pagination."""
        for i in range(1, 6):
            await insert_user(f"Alice {i}", f"alice{i}@example.com", get_test_password_hash())
        
        users, total = await search_users(query="Alice", skip=2, limit=2)
        
        assert len(users) == 2
        assert total == 5


@pytest.mark.asyncio
class TestInsertUsers:
    """Test insert_users (batch) CRUD function."""
    
    async def test_insert_users_success(self, test_db_engine):
        """Test successful batch user insertion."""
        from app.auth import hash_password
        hashed_pw = hash_password("password123")
        items = [
            {"name": "User 1", "email": "user1@example.com", "hashed_password": hashed_pw},
            {"name": "User 2", "email": "user2@example.com", "hashed_password": hashed_pw},
            {"name": "User 3", "email": "user3@example.com", "hashed_password": hashed_pw},
        ]
        
        users = await insert_users(items)
        
        assert len(users) == 3
        assert all(user.id is not None for user in users)
        assert users[0].name == "User 1"
        assert users[1].name == "User 2"
        assert users[2].name == "User 3"
    
    async def test_insert_users_empty_list(self, test_db_engine):
        """Test batch insertion with empty list."""
        users = await insert_users([])
        assert users == []
    
    async def test_insert_users_duplicate_in_batch(self, test_db_engine):
        """Test that duplicates within the batch raise ValueError."""
        from app.auth import hash_password
        hashed_pw = hash_password("password123")
        items = [
            {"name": "User 1", "email": "user1@example.com", "hashed_password": hashed_pw},
            {"name": "User 1 Dup", "email": "user1@example.com", "hashed_password": hashed_pw},  # Duplicate
            {"name": "User 2", "email": "user2@example.com", "hashed_password": hashed_pw},
        ]
        
        with pytest.raises(ValueError, match="duplicate email"):
            await insert_users(items)
    
    async def test_insert_users_chunking(self, test_db_engine):
        """Test that batch insertion works with large batches (chunking)."""
        from app.auth import hash_password
        hashed_pw = hash_password("password123")
        # Create 150 users (will be split into chunks of 100)
        items = [{"name": f"User {i}", "email": f"user{i}@example.com", "hashed_password": hashed_pw} for i in range(150)]
        
        users = await insert_users(items)
        
        assert len(users) == 150
        assert all(user.id is not None for user in users)


@pytest.mark.asyncio
class TestDeleteUsers:
    """Test delete_users (batch) CRUD function."""
    
    async def test_delete_users_success(self, test_db_engine):
        """Test successful batch user deletion."""
        user1 = await insert_user("User 1", "user1@example.com", get_test_password_hash())
        user2 = await insert_user("User 2", "user2@example.com", get_test_password_hash())
        user3 = await insert_user("User 3", "user3@example.com", get_test_password_hash())
        
        deleted = await delete_users([user1.id, user2.id])
        
        assert len(deleted) == 2
        assert any(u.id == user1.id for u in deleted)
        assert any(u.id == user2.id for u in deleted)
        
        # Verify users are actually deleted
        assert await select_user(user1.id) is None
        assert await select_user(user2.id) is None
        assert await select_user(user3.id) is not None  # Not deleted
    
    async def test_delete_users_empty_list(self, test_db_engine):
        """Test batch deletion with empty list."""
        deleted = await delete_users([])
        assert deleted == []
    
    async def test_delete_users_non_existent_ids(self, test_db_engine):
        """Test batch deletion with non-existent IDs."""
        deleted = await delete_users([99999, 88888])
        assert deleted == []
    
    async def test_delete_users_mixed_ids(self, test_db_engine):
        """Test batch deletion with mix of existing and non-existent IDs."""
        user1 = await insert_user("User 1", "user1@example.com", get_test_password_hash())
        
        deleted = await delete_users([user1.id, 99999])
        
        assert len(deleted) == 1
        assert deleted[0].id == user1.id
    
    async def test_delete_users_chunking(self, test_db_engine):
        """Test that batch deletion works with large batches (chunking)."""
        # Create 150 users
        user_ids = []
        for i in range(150):
            user = await insert_user(f"User {i}", f"user{i}@example.com", get_test_password_hash())
            user_ids.append(user.id)
        
        deleted = await delete_users(user_ids)
        
        assert len(deleted) == 150
        
        # Verify all are deleted
        for user_id in user_ids:
            assert await select_user(user_id) is None
