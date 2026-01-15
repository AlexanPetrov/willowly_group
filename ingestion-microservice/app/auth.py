"""JWT authentication validation aligned with User/RAG services."""

from jose import jwt, JWTError
from config import settings


def decode_access_token(token: str) -> dict:
    """Decode and verify JWT token, ensuring valid signature and 'sub' claim presence.
    
    Args:
        token: JWT token string
        
    Returns:
        Payload dict containing token claims (user_id in 'sub')
        
    Raises:
        ValueError: If token is invalid, expired, or missing 'sub' claim
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        # Ensure subject (user_id) is present
        if not payload.get("sub"):
            raise ValueError("Missing subject (sub) in token")
        return payload
    except JWTError as e:
        raise ValueError(f"Token validation failed: {str(e)}")
