# Business logic layer - RULES UNIQUE TO THIS APP

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
from fastapi import HTTPException
from .logger import logger


async def get_user(user_id: int) -> UserOut:
    """Retrieve a user by ID with caching. Raises HTTP 404 if not found."""
    logger.debug(f"Fetching user: id={user_id}")
    
    # Try cache first if enabled
    if settings.CACHE_ENABLED:
        cache_key = make_cache_key(USER_BY_ID_PREFIX, user_id)
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for user: id={user_id}")
            return UserOut(**cached_data)
    
    # Cache miss or disabled - fetch from DB
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
    user_out = UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
    )
    
    # Store in cache if enabled
    if settings.CACHE_ENABLED:
        await cache_manager.set(cache_key, user_out.model_dump())
        # Also cache by email for faster email lookups
        email_cache_key = make_cache_key(USER_BY_EMAIL_PREFIX, user.email)
        await cache_manager.set(email_cache_key, user_out.model_dump())
    
    return user_out


async def delete_user(user_id: int) -> UserOut:
    """Delete a user by ID and invalidate cache. Raises HTTP 404 if not found."""
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
    
    # Invalidate cache for this user
    if settings.CACHE_ENABLED:
        await cache_manager.delete(make_cache_key(USER_BY_ID_PREFIX, user.id))
        await cache_manager.delete(make_cache_key(USER_BY_EMAIL_PREFIX, user.email))
    
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def list_users(
    page: int = settings.DEFAULT_PAGE, # pagination
    limit: int = settings.DEFAULT_LIMIT, # pagination
    email: str | None = None, # filter by email
    email_domain: str | None = None, # filter by email domain
    sort: str = "id",
    order: str = "asc",
) -> PaginatedUserResponse:
    """List users with pagination, optional filters, and sorting."""
    # Validate inputs
    if page < 1:
        page = settings.DEFAULT_PAGE
    # clamp limit between 1 and MAX_LIMIT
    if limit < 1:
        limit = settings.DEFAULT_LIMIT
    if limit > settings.MAX_LIMIT:
        limit = settings.MAX_LIMIT
    # Validate sort field
    if sort not in ["id", "name", "email"]:
        sort = "id"
    # Validate order
    if order not in ["asc", "desc"]:
        order = "asc"
    # Calculate skip (0-indexed offset)
    skip = (page - 1) * limit # convert page num into offset (how many rows to skip)
    # Fetch from CRUD with optional filters and sorting
    logger.debug(f"Listing users: page={page} limit={limit} filters=(email={email}, domain={email_domain}) sort={sort} order={order}")
    users, total = await crud_list_users(skip, limit, email=email, email_domain=email_domain, sort=sort, order=order)
    # Calculate pages
    pages = (total + limit - 1) // limit  # Ceiling division
    logger.debug(f"Found {len(users)} users (total={total})")
    # Convert ORM objects to Pydantic schemas
    items = [
        UserOut(
            id=u.id,
            name=u.name,
            email=u.email,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
    return PaginatedUserResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


async def batch_create_users(data: BatchCreateRequest) -> BatchCreateResponse:
    """Create multiple users in a single request.
    Returns created users and a count. On duplicate email in the DB, raises HTTP 400.
    Large batches are automatically chunked for efficient processing.
    """
    # Validate batch size
    if len(data.items) > settings.MAX_BATCH_SIZE:
        logger.warning(f"Batch create rejected: size {len(data.items)} exceeds maximum {settings.MAX_BATCH_SIZE}")
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
        # Hash passwords for all users before inserting
        items = [
            {
                "name": u.name,
                "email": u.email,
                "hashed_password": hash_password(u.password)
            }
            for u in data.items
        ]
        users = await crud_insert_users(items)
        created_items = [
            UserOut(
                id=u.id,
                name=u.name,
                email=u.email,
                is_active=u.is_active,
                created_at=u.created_at,
            )
            for u in users
        ]
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
    """Delete multiple users by id and return deleted snapshots and count.
    Large batches are automatically chunked for efficient processing.
    """
    # Validate batch size
    if len(req.ids) > settings.MAX_BATCH_SIZE:
        logger.warning(f"Batch delete rejected: size {len(req.ids)} exceeds maximum {settings.MAX_BATCH_SIZE}")
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
    
    # Invalidate cache for deleted users
    if settings.CACHE_ENABLED:
        for user in deleted:
            user_id_key = make_cache_key(USER_BY_ID_PREFIX, user.id)
            user_email_key = make_cache_key(USER_BY_EMAIL_PREFIX, user.email)
            await cache_manager.delete(user_id_key)
            await cache_manager.delete(user_email_key)
    
    logger.info(f"Batch delete completed: {len(deleted)} users deleted")
    items = [
        UserOut(
            id=u.id,
            name=u.name,
            email=u.email,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in deleted
    ]
    return BatchDeleteResponse(items=items, deleted=len(items))


async def search_users(
    q: str,
    page: int = settings.DEFAULT_PAGE,
    limit: int = settings.DEFAULT_LIMIT,
    sort: str = "id",
    order: str = "asc",
) -> PaginatedUserResponse:
    """Search users by name or email with pagination and sorting."""
    # Validate inputs
    if page < 1:
        page = settings.DEFAULT_PAGE
    if limit < 1:
        limit = settings.DEFAULT_LIMIT
    if limit > settings.MAX_LIMIT:
        limit = settings.MAX_LIMIT
    if sort not in ["id", "name", "email"]:
        sort = "id"
    if order not in ["asc", "desc"]:
        order = "asc"
    
    skip = (page - 1) * limit
    logger.info(f"Searching users: query='{q}' page={page} limit={limit}")
    users, total = await crud_search_users(q, skip, limit, sort, order)
    pages = (total + limit - 1) // limit
    logger.info(f"Search completed: found {total} matching users")
    items = [
        UserOut(
            id=u.id,
            name=u.name,
            email=u.email,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
    return PaginatedUserResponse(items=items, total=total, page=page, limit=limit, pages=pages)


async def register_user(data: UserRegister) -> UserOut:
    """Register a new user with password authentication and cache it.
    
    Creates a new user account with hashed password. Raises HTTP 400 on duplicate email.
    
    Args:
        data: UserRegister schema containing name, email, and password
        
    Returns:
        UserOut: The created user data (without password)
        
    Raises:
        HTTPException: 400 if email already exists
    """
    logger.info(f"Registering new user: {data.email}")
    
    # Check if email already exists (check DB, not cache)
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
    
    # Hash the password
    hashed_password = hash_password(data.password)
    
    # Create the user
    try:
        user = await insert_user(data.name, data.email, hashed_password)
        logger.info(f"User registered successfully: id={user.id} email={user.email}")
        
        user_out = UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        
        # Cache the new user
        if settings.CACHE_ENABLED:
            await cache_manager.set(
                make_cache_key(USER_BY_ID_PREFIX, user.id),
                user_out.model_dump()
            )
            await cache_manager.set(
                make_cache_key(USER_BY_EMAIL_PREFIX, user.email),
                user_out.model_dump()
            )
        
        return user_out
    except ValueError as e:
        # This should be rare since we already checked for duplicates
        logger.error(f"Unexpected error during registration for {data.email}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ErrorCode.DUPLICATE_EMAIL,
                "message": f"User with email '{data.email}' already exists",
                "details": {"email": data.email}
            }
        ) from e


async def _get_user_by_email_with_cache(email: str):
    """Internal helper to get user by email with caching.
    
    Returns the full User model (including hashed_password) for authentication.
    """
    # Try cache first if enabled
    if settings.CACHE_ENABLED:
        cache_key = make_cache_key(USER_BY_EMAIL_PREFIX, email)
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            # Cache only has UserOut data, need to fetch from DB for password
            # So we only use cache as a hint that user exists
            pass
    
    # Fetch from DB (we need the hashed_password which isn't cached)
    return await select_user_by_email(email)


async def authenticate_user(data: UserLogin) -> Token:
    """Authenticate a user and return a JWT access token.
    
    Verifies user credentials and generates a JWT token for authenticated requests.
    
    Args:
        data: UserLogin schema containing email and password
        
    Returns:
        Token: JWT access token and token type
        
    Raises:
        HTTPException: 401 if credentials are invalid or user is inactive
    """
    logger.info(f"Authentication attempt for user: {data.email}")
    
    # Fetch user by email (no cache for auth - need password hash)
    user = await select_user_by_email(data.email)
    
    # Verify user exists
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
    
    # Verify password
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
    
    # Check if user is active
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
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info(f"Authentication successful for user: {data.email} (id={user.id})")
    
    return Token(access_token=access_token, token_type="bearer")
