"""JWT validation aligned with User Microservice settings (HS256 by secret)."""

from jose import jwt, JWTError
from .config import settings


def decode_access_token(token: str) -> dict:
    """Decode and verify JWT token, ensuring valid signature and 'sub' claim presence."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Ensure subject is present
        if not payload.get("sub"):
            raise ValueError("Missing subject (sub) in token")
        return payload
    except JWTError as e:
        raise ValueError(f"Token validation failed: {str(e)}")
