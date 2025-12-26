"""Unit tests for JWT authentication."""

import pytest
from jose import jwt
from app.auth import decode_access_token


def test_decode_valid_token(valid_token):
    """Test decoding a valid JWT token returns payload."""
    payload = decode_access_token(valid_token)
    
    assert payload is not None
    assert payload["sub"] == "test-user-123"
    assert payload["email"] == "test@example.com"


def test_decode_expired_token(expired_token):
    """Test decoding an expired token raises ValueError."""
    with pytest.raises(ValueError, match="Token validation failed"):
        decode_access_token(expired_token)


def test_decode_token_missing_sub(token_missing_sub):
    """Test decoding token without 'sub' claim raises ValueError."""
    with pytest.raises(ValueError, match=r"Missing subject \(sub\) in token"):
        decode_access_token(token_missing_sub)


def test_decode_invalid_signature():
    """Test decoding token with invalid signature raises ValueError."""
    # Create token with wrong secret
    payload = {"sub": "test-user-123", "email": "test@example.com"}
    invalid_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
    
    with pytest.raises(ValueError, match="Token validation failed"):
        decode_access_token(invalid_token)


def test_decode_malformed_token():
    """Test decoding malformed token raises ValueError."""
    with pytest.raises(ValueError, match="Token validation failed"):
        decode_access_token("not.a.valid.token")


def test_decode_empty_token():
    """Test decoding empty token raises ValueError."""
    with pytest.raises(ValueError, match="Token validation failed"):
        decode_access_token("")
