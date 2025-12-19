"""
Tests for security headers middleware.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Test that all required security headers are present in responses."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    
    # Check all security headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    assert "Permissions-Policy" in response.headers


@pytest.mark.asyncio
async def test_security_headers_on_all_endpoints(client: AsyncClient):
    """Test that security headers are applied to all endpoints."""
    endpoints = [
        "/",
        "/health",
        "/metrics",
    ]
    
    for endpoint in endpoints:
        response = await client.get(endpoint)
        
        # All endpoints should have security headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_hsts_header_not_in_dev(client: AsyncClient):
    """Test that HSTS header is not set in dev/test environments."""
    response = await client.get("/health")
    
    # HSTS should only be in production
    # In test/dev mode, it should not be present
    hsts = response.headers.get("Strict-Transport-Security")
    # Should be None in test environment
    assert hsts is None


@pytest.mark.asyncio
async def test_csp_header_content(client: AsyncClient):
    """Test that Content Security Policy header has correct directives."""
    response = await client.get("/health")
    
    csp = response.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "script-src" in csp
    assert "style-src" in csp


@pytest.mark.asyncio
async def test_security_headers_on_error_responses(client: AsyncClient):
    """Test that security headers are present even on error responses."""
    # Try to access non-existent endpoint
    response = await client.get("/nonexistent")
    
    assert response.status_code == 404
    
    # Security headers should still be present
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.asyncio
async def test_security_headers_on_post_requests(client: AsyncClient):
    """Test that security headers are present on POST requests."""
    # Make a POST request (even if it fails, headers should be there)
    response = await client.post("/auth/register", json={
        "name": "Test User",
        "email": "security-test@example.com",
        "password": "SecurePass123!"
    })
    
    # Should have security headers regardless of response status
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
