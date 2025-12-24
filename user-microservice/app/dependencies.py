"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .auth import decode_access_token
from .crud import select_user
from .models import User
from .schemas import ErrorCode


# ==================== Authentication Dependencies ====================

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get authenticated user from JWT token. Raises 401 if invalid/expired, 403 if inactive."""
    # Extract token from Authorization header
    token = credentials.credentials
    
    # Decode and validate token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "Invalid or expired authentication token",
                "details": {}
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user_id from token payload
    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "Token payload is invalid",
                "details": {}
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    user = await select_user(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": ErrorCode.USER_NOT_FOUND,
                "message": "User not found",
                "details": {"user_id": user_id}
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": ErrorCode.INVALID_INPUT,
                "message": "User account is inactive",
                "details": {"user_id": user_id}
            },
        )
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Alias for get_current_user (already validates active status)."""
    return current_user
