"""
Integration tests for User Microservice API endpoints.
Tests all CRUD operations, pagination, filtering, search, and batch operations.
"""

import pytest


# ============================================================================
# POST /auth/register - Create User with Authentication
# ============================================================================

@pytest.mark.asyncio
async def test_create_user_success(client, sample_user):
    """Test creating a valid user returns 201 with user data."""
    response = await client.post("/auth/register", json=sample_user)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_user["name"]
    assert data["email"] == sample_user["email"]
    assert "id" in data
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client, sample_user):
    """Test creating user with duplicate email returns 400."""
    # Create first user
    await client.post("/auth/register", json=sample_user)
    
    # Try to create duplicate
    response = await client.post("/auth/register", json=sample_user)
    
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "DUPLICATE_EMAIL"
    assert "already exists" in detail["message"]


@pytest.mark.asyncio
async def test_create_user_invalid_email(client):
    """Test creating user with invalid email returns 422."""
    response = await client.post("/auth/register", json={
        "name": "Test User",
        "email": "not-an-email",
        "password": "password123"
    })
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_missing_name(client):
    """Test creating user without name returns 422."""
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_missing_email(client):
    """Test creating user without email returns 422."""
    response = await client.post("/auth/register", json={
        "name": "Test User",
        "password": "password123"
    })
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_name_too_long(client):
    """Test creating user with name exceeding max length returns 422."""
    long_name = "A" * 101  # Exceeds USER_NAME_MAX_LENGTH (100)
    response = await client.post("/auth/register", json={
        "name": long_name,
        "email": "test@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("name" in str(error).lower() for error in detail)


@pytest.mark.asyncio
async def test_create_user_email_too_long(client):
    """Test creating user with email exceeding max length returns 422."""
    # Create email with 256+ characters (exceeds USER_EMAIL_MAX_LENGTH of 255)
    long_email = "a" * 243 + "@example.com"  # Total 255 chars (at limit)
    # Add one more character to exceed
    long_email = "a" * 244 + "@example.com"  # Total 256 chars (exceeds limit)
    response = await client.post("/auth/register", json={
        "name": "Test User",
        "email": long_email,
        "password": "password123"
    })
    
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("email" in str(error).lower() for error in detail)


@pytest.mark.asyncio
async def test_create_user_whitespace_name(client):
    """Test creating user with only whitespace name returns 422."""
    response = await client.post("/auth/register", json={
        "name": "   ",
        "email": "test@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_name_trimmed(client):
    """Test that whitespace is trimmed from user name."""
    response = await client.post("/auth/register", json={
        "name": "  John Doe  ",
        "email": "john@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Doe"  # Should be trimmed


# ============================================================================
# GET /users/{user_id} - Read User
# ============================================================================

@pytest.mark.asyncio
async def test_get_user_success(client, sample_user):
    """Test getting existing user returns 200 with user data."""
    # Create user first
    create_response = await client.post("/auth/register", json=sample_user)
    user_id = create_response.json()["id"]
    
    # Get user
    response = await client.get(f"/users/{user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["name"] == sample_user["name"]
    assert data["email"] == sample_user["email"]


@pytest.mark.asyncio
async def test_get_user_not_found(client):
    """Test getting non-existent user returns 404."""
    response = await client.get("/users/99999")
    
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "USER_NOT_FOUND"
    assert "does not exist" in detail["message"]


@pytest.mark.asyncio
async def test_get_user_invalid_id(client):
    """Test getting user with invalid ID format returns 422."""
    response = await client.get("/users/invalid")
    
    assert response.status_code == 422


# ============================================================================
# DELETE /users/{user_id} - Delete User
# ============================================================================

@pytest.mark.asyncio
async def test_delete_user_success(client, sample_user):
    """Test deleting existing user returns 200 with deleted user data."""
    # Create user first
    create_response = await client.post("/auth/register", json=sample_user)
    user_id = create_response.json()["id"]
    
    # Delete user
    response = await client.delete(f"/users/{user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == sample_user["email"]
    
    # Verify user is deleted
    get_response = await client.get(f"/users/{user_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_not_found(client):
    """Test deleting non-existent user returns 404."""
    response = await client.delete("/users/99999")
    
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "USER_NOT_FOUND"
    assert "does not exist" in detail["message"]


# ============================================================================
# GET /users - List Users
# ============================================================================

@pytest.mark.asyncio
async def test_list_users_empty(client):
    """Test listing users in empty database returns empty list."""
    response = await client.get("/users")
    
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0


@pytest.mark.asyncio
async def test_list_users_default_pagination(client, sample_users):
    """Test listing users with default pagination."""
    # Create multiple users
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == len(sample_users)
    assert data["total"] == len(sample_users)
    assert data["page"] == 1
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_list_users_custom_pagination(client, sample_users):
    """Test listing users with custom page and limit."""
    # Create multiple users
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?page=2&limit=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2
    assert data["limit"] == 2
    assert data["total"] == len(sample_users)


@pytest.mark.asyncio
async def test_list_users_limit_exceeds_max(client, sample_users):
    """Test listing users with limit exceeding MAX_LIMIT is clamped to 100."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?limit=999")
    
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 100  # Clamped to MAX_LIMIT


@pytest.mark.asyncio
async def test_list_users_invalid_page(client, sample_users):
    """Test listing users with invalid page defaults to 1."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?page=0")
    
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_users_filter_by_email(client, sample_users):
    """Test filtering users by exact email."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    target_email = sample_users[0]["email"]
    response = await client.get(f"/users?email={target_email}")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["email"] == target_email


@pytest.mark.asyncio
async def test_list_users_filter_by_domain(client, sample_users):
    """Test filtering users by email domain."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?email_domain=example.com")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(sample_users)
    for item in data["items"]:
        assert "@example.com" in item["email"]


@pytest.mark.asyncio
async def test_list_users_sort_by_name_asc(client, sample_users):
    """Test sorting users by name ascending."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?sort=name&order=asc")
    
    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_list_users_sort_by_name_desc(client, sample_users):
    """Test sorting users by name descending."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?sort=name&order=desc")
    
    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert names == sorted(names, reverse=True)


@pytest.mark.asyncio
async def test_list_users_sort_by_email(client, sample_users):
    """Test sorting users by email."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?sort=email&order=asc")
    
    assert response.status_code == 200
    data = response.json()
    emails = [item["email"] for item in data["items"]]
    assert emails == sorted(emails)


@pytest.mark.asyncio
async def test_list_users_invalid_sort_field(client, sample_users):
    """Test invalid sort field defaults to 'id'."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users?sort=invalid_field")
    
    assert response.status_code == 200
    # Should default to sorting by id


# ============================================================================
# GET /users/search - Search Users
# ============================================================================

@pytest.mark.asyncio
async def test_search_users_by_name(client, sample_users):
    """Test searching users by name."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users/search?q=Alice")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_search_users_by_email(client, sample_users):
    """Test searching users by email."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users/search?q=bob@")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert "bob" in data["items"][0]["email"]


@pytest.mark.asyncio
async def test_search_users_case_insensitive(client, sample_users):
    """Test search is case-insensitive."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users/search?q=ALICE")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_search_users_partial_match(client, sample_users):
    """Test search with partial match."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users/search?q=ali")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert "Ali" in data["items"][0]["name"]


@pytest.mark.asyncio
async def test_search_users_no_matches(client, sample_users):
    """Test search with no matches returns empty list."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    response = await client.get("/users/search?q=nonexistent")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_users_special_characters(client, sample_user):
    """Test search properly escapes special SQL LIKE characters."""
    # Create user with special chars in name
    special_user = {"name": "User_100%", "email": "special@example.com", "password": "password123"}
    await client.post("/auth/register", json=special_user)
    
    # Search should find literal % and _ characters
    response = await client.get("/users/search?q=100%")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "User_100%"


@pytest.mark.asyncio
async def test_search_users_with_pagination(client, sample_users):
    """Test search with pagination."""
    for user in sample_users:
        await client.post("/auth/register", json=user)
    
    # Search for common substring
    response = await client.get("/users/search?q=example.com&page=1&limit=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["limit"] == 2


# ============================================================================
# POST /users/batch-create - Batch Create Users
# ============================================================================

@pytest.mark.asyncio
async def test_batch_create_success(client, sample_users):
    """Test batch creating multiple users."""
    response = await client.post("/users/batch-create", json={"items": sample_users})
    
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == len(sample_users)
    assert len(data["items"]) == len(sample_users)
    for item in data["items"]:
        assert "id" in item
        assert isinstance(item["id"], int)


@pytest.mark.asyncio
async def test_batch_create_empty(client):
    """Test batch create with empty list."""
    response = await client.post("/users/batch-create", json={"items": []})
    
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_batch_create_exceeds_max_size(client):
    """Test batch create exceeding MAX_BATCH_SIZE returns 400."""
    # Create 1001 users (exceeds MAX_BATCH_SIZE of 1000)
    large_batch = [
        {"name": f"User{i}", "email": f"user{i}@example.com", "password": "password123"}
        for i in range(1001)
    ]
    
    response = await client.post("/users/batch-create", json={"items": large_batch})
    
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "BATCH_SIZE_EXCEEDED"
    assert "exceeds maximum" in detail["message"]


@pytest.mark.asyncio
async def test_batch_create_duplicate_email(client, sample_user):
    """Test batch create with duplicate email returns 400."""
    # Create initial user
    await client.post("/auth/register", json=sample_user)
    
    # Try to batch create with duplicate
    batch = [sample_user, {"name": "Another", "email": "another@example.com", "password": "password123"}]
    response = await client.post("/users/batch-create", json={"items": batch})
    
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "DUPLICATE_EMAIL"
    assert "already exist" in detail["message"]


@pytest.mark.asyncio
async def test_batch_create_chunking(client):
    """Test batch create with more than CHUNK_SIZE (100) works correctly."""
    # Create 150 users to test chunking
    large_batch = [
        {"name": f"User{i}", "email": f"user{i}@example.com", "password": "password123"}
        for i in range(150)
    ]
    
    response = await client.post("/users/batch-create", json={"items": large_batch})
    
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 150
    assert len(data["items"]) == 150


# ============================================================================
# POST /users/batch-delete - Batch Delete Users
# ============================================================================

@pytest.mark.asyncio
async def test_batch_delete_success(client, sample_users):
    """Test batch deleting multiple users."""
    # Create users first
    user_ids = []
    for user in sample_users:
        response = await client.post("/auth/register", json=user)
        user_ids.append(response.json()["id"])
    
    # Batch delete
    response = await client.post("/users/batch-delete", json={"ids": user_ids})
    
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == len(user_ids)
    assert len(data["items"]) == len(user_ids)
    
    # Verify all users are deleted
    for user_id in user_ids:
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_batch_delete_empty(client):
    """Test batch delete with empty list."""
    response = await client.post("/users/batch-delete", json={"ids": []})
    
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_batch_delete_non_existent_ids(client):
    """Test batch delete with non-existent IDs returns empty items."""
    response = await client.post("/users/batch-delete", json={"ids": [99999, 88888]})
    
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_batch_delete_mixed_ids(client, sample_users):
    """Test batch delete with mix of existing and non-existent IDs."""
    # Create some users
    user_ids = []
    for user in sample_users[:2]:
        response = await client.post("/auth/register", json=user)
        user_ids.append(response.json()["id"])
    
    # Add non-existent IDs
    mixed_ids = user_ids + [99999, 88888]
    
    response = await client.post("/users/batch-delete", json={"ids": mixed_ids})
    
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 2  # Only existing users deleted
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_batch_delete_exceeds_max_size(client):
    """Test batch delete exceeding MAX_BATCH_SIZE returns 400."""
    # Create 1001 IDs (exceeds MAX_BATCH_SIZE of 1000)
    large_batch = list(range(1, 1002))
    
    response = await client.post("/users/batch-delete", json={"ids": large_batch})
    
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "BATCH_SIZE_EXCEEDED"
    assert "exceeds maximum" in detail["message"]
