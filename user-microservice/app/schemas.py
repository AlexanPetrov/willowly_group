# Pydantic models for request/response VALIDATION & serialization

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from .config import USER_NAME_MAX_LENGTH, USER_EMAIL_MAX_LENGTH


# Error Response Schema
class ErrorResponse(BaseModel):
    """Standardized error response with code and message."""
    error: str  # Error code (e.g., "USER_NOT_FOUND")
    message: str  # Human-readable message
    details: dict | None = None  # Optional additional context


# Error Codes
class ErrorCode:
    """Centralized error codes for API responses."""
    USER_NOT_FOUND = "USER_NOT_FOUND"
    DUPLICATE_EMAIL = "DUPLICATE_EMAIL"
    BATCH_SIZE_EXCEEDED = "BATCH_SIZE_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"


class UserOut(BaseModel):
    id: int
    name: str = Field(..., max_length=USER_NAME_MAX_LENGTH)
    email: EmailStr = Field(..., max_length=USER_EMAIL_MAX_LENGTH)
    is_active: bool
    created_at: datetime


# Authentication Schemas
class UserRegister(BaseModel):
    """Schema for user registration with password."""
    name: str = Field(..., min_length=1, max_length=USER_NAME_MAX_LENGTH, description="User's full name")
    email: EmailStr = Field(..., max_length=USER_EMAIL_MAX_LENGTH, description="User's email address")
    password: str = Field(..., min_length=8, max_length=100, description="User's password (min 8 characters)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not just whitespace."""
        if not v.strip():
            raise ValueError("Name cannot be empty or only whitespace")
        return v.strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        # Add more complexity requirements if needed
        return v


class UserLogin(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: int | None = None


class PaginatedUserResponse(BaseModel): # pagination
    items: list[UserOut]
    total: int
    page: int
    limit: int
    pages: int


class BatchCreateRequest(BaseModel):
    items: list[UserRegister]


class BatchCreateResponse(BaseModel):
    items: list[UserOut]
    created: int


class BatchDeleteRequest(BaseModel):
    ids: list[int]


class BatchDeleteResponse(BaseModel):
    items: list[UserOut]
    deleted: int
