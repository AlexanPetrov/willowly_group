"""Business logic layer for user operations with caching and validation.

Handles user CRUD operations, authentication, batch operations, and search.
Implements caching strategy for frequently accessed user data.
"""

from .schemas import (
    UserOut,
    PaginatedUserResponse,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchDeleteRequest,
    BatchDeleteResponse,
    UserRegister,
    UserLogin,
    Token,
    ErrorCode,
)
from .crud import (
    insert_user,
    select_user,
    select_user_by_email,
    list_users as crud_list_users,
    delete_user as crud_delete_user,
    insert_users as crud_insert_users,
    delete_users as crud_delete_users,
    search_users as crud_search_users,
)
from .auth import hash_password, verify_password, create_access_token
from .cache import cache_manager, make_cache_key, USER_BY_ID_PREFIX, USER_BY_EMAIL_PREFIX
from .config import settings
from .models import User
from fastapi import HTTPException
from .logger import logger

# ==================== Helper Functions ====================


def _convert_to_user_out(user: User) -> UserOut:
    """Convert ORM User model to UserOut schema."""
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _validate_pagination(page: int, limit: int) -> tuple[int, int, int]:
    """Validate and normalize pagination parameters.
    
    Returns:
        tuple: (page, limit, skip) normalized values
    """
    if page < 1:
        page = settings.DEFAULT_PAGE
    if limit < 1:
        limit = settings.DEFAULT_LIMIT
    if limit > settings.MAX_LIMIT:
        limit = settings.MAX_LIMIT
    skip = (page - 1) * limit
    return page, limit, skip


def _validate_sort_params(sort: str, order: str) -> tuple[str, str]:
    """Validate and normalize sort parameters.
    
    Returns:
        tuple: (sort, order) normalized values
    """
    if sort not in ["id", "name", "email"]:
        sort = "id"
    if order not in ["asc", "desc"]:
        order = "asc"
    return sort, order


async def _cache_user(user_out: UserOut) -> None:
    """Cache user data by both ID and email if caching is enabled."""
    if settings.CACHE_ENABLED:
        await cache_manager.set(
            make_cache_key(USER_BY_ID_PREFIX, user_out.id),
            user_out.model_dump()
        )
        await cache_manager.set(
            make_cache_key(USER_BY_EMAIL_PREFIX, user_out.email),
            user_out.model_dump()
        )


async def _invalidate_user_cache(user: User) -> None:
    """Invalidate cached user data by both ID and email if caching is enabled."""
    if settings.CACHE_ENABLED:
        await cache_manager.delete(make_cache_key(USER_BY_ID_PREFIX, user.id))
        await cache_manager.delete(make_cache_key(USER_BY_EMAIL_PREFIX, user.email))


# ==================== User Operations ====================


async def get_user(user_id: int) -> UserOut:
    """Retrieve a user by ID with caching."""
    logger.debug(f"Fetching user: id={user_id}")
    
    if settings.CACHE_ENABLED:
        cache_key = make_cache_key(USER_BY_ID_PREFIX, user_id)
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for user: id={user_id}")
            return UserOut(**cached_data)
    
    user = await select_user(user_id)
    if not user:
        logger.warning(f"User not found: id={user_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": ErrorCode.USER_NOT_FOUND,
                "message": f"User with ID {user_id} does not exist",
                "details": {"user_id": user_id}
            }
        )
    
    logger.debug(f"User retrieved from DB: id={user.id} email={user.email}")
    user_out = _convert_to_user_out(user)
    await _cache_user(user_out)
    
    return user_out


async def delete_user(user_id: int) -> UserOut:
    """Delete a user by ID and invalidate cache."""
    logger.info(f"Deleting user: id={user_id}")
    user = await crud_delete_user(user_id)
    if not user:
        logger.warning(f"Cannot delete - user not found: id={user_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": ErrorCode.USER_NOT_FOUND,
                "message": f"Cannot delete user with ID {user_id}: user does not exist",
                "details": {"user_id": user_id}
            }
        )
    
    logger.info(f"User deleted successfully: id={user.id} email={user.email}")
    await _invalidate_user_cache(user)
    
    return _convert_to_user_out(user)


async def list_users(
    page: int = settings.DEFAULT_PAGE,
    limit: int = settings.DEFAULT_LIMIT,
    email: str | None = None,
    email_domain: str | None = None,
    sort: str = "id",
    order: str = "asc",
) -> PaginatedUserResponse:
    """List users with pagination, optional filters, and sorting."""
    page, limit, skip = _validate_pagination(page, limit)
    sort, order = _validate_sort_params(sort, order)
    
    logger.debug(
        f"Listing users: page={page} limit={limit} "
        f"filters=(email={email}, domain={email_domain}) sort={sort} order={order}"
    )
    
    users, total = await crud_list_users(
        skip, limit, email=email, email_domain=email_domain, sort=sort, order=order
    )
    
    pages = (total + limit - 1) // limit
    logger.debug(f"Found {len(users)} users (total={total})")
    
    items = [_convert_to_user_out(u) for u in users]
    
    return PaginatedUserResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )

# ==================== Batch Operations ====================


async def batch_create_users(data: BatchCreateRequest) -> BatchCreateResponse:
    """Create multiple users in a single request with automatic chunking."""
    if len(data.items) > settings.MAX_BATCH_SIZE:
        logger.warning(
            f"Batch create rejected: size {len(data.items)} exceeds maximum {settings.MAX_BATCH_SIZE}"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.BATCH_SIZE_EXCEEDED,
                "message": f"Batch size {len(data.items)} exceeds maximum allowed size of {settings.MAX_BATCH_SIZE}",
                "details": {"provided": len(data.items), "maximum": settings.MAX_BATCH_SIZE}
            }
        )
    
    logger.info(f"Batch creating {len(data.items)} users")
    
    try:
        items = [
            {
                "name": u.name,
                "email": u.email,
                "hashed_password": hash_password(u.password)
            }
            for u in data.items
        ]
        users = await crud_insert_users(items)
        created_items = [_convert_to_user_out(u) for u in users]
        
        logger.info(f"Batch create completed: {len(created_items)} users created")
        return BatchCreateResponse(items=created_items, created=len(created_items))
    except ValueError as e:
        logger.error(f"Batch create failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.DUPLICATE_EMAIL,
                "message": "Batch create failed: one or more email addresses already exist in the database",
                "details": {"reason": str(e)}
            }
        ) from e


async def batch_delete_users(req: BatchDeleteRequest) -> BatchDeleteResponse:
    """Delete multiple users by ID with batch cache invalidation."""
    if len(req.ids) > settings.MAX_BATCH_SIZE:
        logger.warning(
            f"Batch delete rejected: size {len(req.ids)} exceeds maximum {settings.MAX_BATCH_SIZE}"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.BATCH_SIZE_EXCEEDED,
                "message": f"Batch size {len(req.ids)} exceeds maximum allowed size of {settings.MAX_BATCH_SIZE}",
                "details": {"provided": len(req.ids), "maximum": settings.MAX_BATCH_SIZE}
            }
        )
    
    logger.info(f"Batch deleting {len(req.ids)} users")
    deleted = await crud_delete_users(req.ids)
    
    # Batch invalidate cache
    if settings.CACHE_ENABLED:
        for user in deleted:
            await _invalidate_user_cache(user)
    
    logger.info(f"Batch delete completed: {len(deleted)} users deleted")
    items = [_convert_to_user_out(u) for u in deleted]
    
    return BatchDeleteResponse(items=items, deleted=len(items))

# ==================== Search ====================


async def search_users(
    q: str,
    page: int = settings.DEFAULT_PAGE,
    limit: int = settings.DEFAULT_LIMIT,
    sort: str = "id",
    order: str = "asc",
) -> PaginatedUserResponse:
    """Search users by name or email with pagination and sorting."""
    page, limit, skip = _validate_pagination(page, limit)
    sort, order = _validate_sort_params(sort, order)
    
    logger.info(f"Searching users: query='{q}' page={page} limit={limit}")
    users, total = await crud_search_users(q, skip, limit, sort, order)
    pages = (total + limit - 1) // limit
    logger.info(f"Search completed: found {total} matching users")
    
    items = [_convert_to_user_out(u) for u in users]
    
    return PaginatedUserResponse(
        items=items, total=total, page=page, limit=limit, pages=pages
    )

# ==================== Authentication ====================


async def register_user(data: UserRegister) -> UserOut:
    """Register a new user with password authentication and caching."""
    logger.info(f"Registering new user: {data.email}")
    
    existing_user = await select_user_by_email(data.email)
    if existing_user:
        logger.warning(f"Registration failed - email already exists: {data.email}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.DUPLICATE_EMAIL,
                "message": f"User with email '{data.email}' already exists",
                "details": {"email": data.email}
            }
        )
    
    hashed_password = hash_password(data.password)
    
    try:
        user = await insert_user(data.name, data.email, hashed_password)
        logger.info(f"User registered successfully: id={user.id} email={user.email}")
        
        user_out = _convert_to_user_out(user)
        await _cache_user(user_out)
        
        return user_out
    except ValueError as e:
        logger.error(f"Unexpected error during registration for {data.email}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.DUPLICATE_EMAIL,
                "message": f"User with email '{data.email}' already exists",
                "details": {"email": data.email}
            }
        ) from e


async def authenticate_user(data: UserLogin) -> Token:
    """Authenticate a user and return a JWT access token."""
    logger.info(f"Authentication attempt for user: {data.email}")
    
    user = await select_user_by_email(data.email)
    
    if not user:
        logger.warning(f"Authentication failed - user not found: {data.email}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "Invalid email or password",
                "details": {}
            }
        )
    
    if not verify_password(data.password, user.hashed_password):
        logger.warning(f"Authentication failed - invalid password for user: {data.email}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "Invalid email or password",
                "details": {}
            }
        )
    
    if not user.is_active:
        logger.warning(f"Authentication failed - user is inactive: {data.email}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "User account is inactive",
                "details": {"email": data.email}
            }
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"Authentication successful for user: {data.email} (id={user.id})")
    
    return Token(access_token=access_token, token_type="bearer")
