"""Authentication utilities for password hashing and JWT token management."""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from .config import settings


# ==================== Password Hashing ====================

def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt for secure storage."""
    # bcrypt requires bytes and returns bytes
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ==================== JWT Token Management ====================

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with optional expiration. Defaults to configured expiration time."""
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Encode and return token
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns payload dict if valid, None if invalid or expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
