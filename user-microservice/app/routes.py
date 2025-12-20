# API route definitions (HTTP layer)
# Defines ENDPOINTS

import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
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
)
from .models import User
from .dependencies import get_current_active_user
from . import services
from .config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Helper to conditionally apply rate limiting (skip in tests)
def conditional_limit(limit_string):
    """Apply rate limit only if not in test mode."""
    if os.getenv('TEST_MODE'):
        # Return a no-op decorator in test mode
        def decorator(func):
            return func
        return decorator
    return limiter.limit(limit_string)


router = APIRouter()

@router.get("/")
def root():
    return {"app": settings.APP_NAME, "env": settings.APP_ENV}


@router.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring.
    
    Returns:
        - 200 OK if service, database, and cache are healthy
        - 503 Service Unavailable if database or cache is unreachable
    """
    from . import db
    from .cache import cache_manager
    
    health_status = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
    
    # Check database connectivity with retry logic
    try:
        is_db_healthy = await db.check_db_connection()
        if is_db_healthy:
            health_status["database"] = "connected"
        else:
            health_status["status"] = "unhealthy"
            health_status["database"] = "disconnected"
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=health_status)
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = f"error: {str(e)}"
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=health_status)
    
    # Check Redis cache connectivity
    if settings.CACHE_ENABLED:
        try:
            is_healthy = await cache_manager.health_check()
            health_status["cache"] = "connected" if is_healthy else "disconnected"
            if not is_healthy:
                health_status["status"] = "degraded"  # Service works but cache is down
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["cache"] = f"error: {str(e)}"
    else:
        health_status["cache"] = "disabled"
    
    return health_status


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/auth/register", response_model=UserOut, status_code=201)
@conditional_limit(settings.RATE_LIMIT_WRITE)
async def register(user: UserRegister, request: Request):
    """Register a new user with email and password.
    
    Args:
        user: UserRegister schema containing name, email, and password
        
    Returns:
        UserOut: The created user data (without password)
        
    Raises:
        400: Email already exists
    """
    return await services.register_user(user)


@router.post("/auth/login", response_model=Token)
@conditional_limit(settings.RATE_LIMIT_WRITE)
async def login(credentials: UserLogin, request: Request):
    """Authenticate a user and return a JWT access token.
    
    Args:
        credentials: UserLogin schema containing email and password
        
    Returns:
        Token: JWT access token and token type
        
    Raises:
        401: Invalid credentials or inactive user
    """
    return await services.authenticate_user(credentials)


@router.get("/users/me", response_model=UserOut)
@conditional_limit(settings.RATE_LIMIT_READ)
async def get_current_user(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """Get the currently authenticated user's profile.
    
    Requires:
        Authorization header with valid JWT Bearer token
        
    Returns:
        UserOut: The authenticated user's data
        
    Raises:
        401: Invalid or expired token
        403: User is inactive
    """
    return UserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


# ============================================================================
# User Management Endpoints
# ============================================================================

@router.post("/users/batch-create", response_model=BatchCreateResponse)
@conditional_limit(settings.RATE_LIMIT_BATCH)
async def batch_create(req: BatchCreateRequest, request: Request):
    return await services.batch_create_users(req)


@router.post("/users/batch-delete", response_model=BatchDeleteResponse)
@conditional_limit(settings.RATE_LIMIT_BATCH)
async def batch_delete(req: BatchDeleteRequest, request: Request):
    return await services.batch_delete_users(req)


@router.get("/users", response_model=PaginatedUserResponse)
@conditional_limit(settings.RATE_LIMIT_READ)
async def list_users(
    request: Request,
    page: int = settings.DEFAULT_PAGE,
    limit: int = settings.DEFAULT_LIMIT,
    email: str | None = None, # filter by email
    email_domain: str | None = None, # filter by email domain
    sort: str = "id",
    order: str = "asc",
):
    return await services.list_users(
        page=page,
        limit=limit,
        email=email,
        email_domain=email_domain,
        sort=sort,
        order=order,
    )


@router.get("/users/search", response_model=PaginatedUserResponse)
@conditional_limit(settings.RATE_LIMIT_READ)
async def search_users(
    request: Request,
    q: str,
    page: int = settings.DEFAULT_PAGE, # pagination
    limit: int = settings.DEFAULT_LIMIT, # pagination
    sort: str = "id",
    order: str = "asc",
):
    return await services.search_users(
        q=q,
        page=page,
        limit=limit,
        sort=sort,
        order=order,
    )


@router.get("/users/{user_id}", response_model=UserOut)
@conditional_limit(settings.RATE_LIMIT_READ)
async def get_user(user_id: int, request: Request):
    return await services.get_user(user_id)


@router.delete("/users/{user_id}", response_model=UserOut)
@conditional_limit(settings.RATE_LIMIT_WRITE)
async def delete_user(user_id: int, request: Request):
    return await services.delete_user(user_id)
