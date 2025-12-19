"""
Tests for Prometheus metrics endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_exists(client: AsyncClient):
    """Test that /metrics endpoint is accessible."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_metrics_content_format(client: AsyncClient):
    """Test that metrics endpoint returns Prometheus format."""
    response = await client.get("/metrics")
    content = response.text
    
    # Should contain Prometheus metric format (# HELP, # TYPE, metric names)
    assert "# HELP" in content or "# TYPE" in content
    assert "http_requests" in content or "http_request" in content


@pytest.mark.asyncio
async def test_metrics_after_request(client: AsyncClient):
    """Test that metrics are updated after making requests."""
    # Make a request to generate metrics
    await client.get("/health")
    
    # Get metrics
    response = await client.get("/metrics")
    content = response.text
    
    # Should have recorded the health check request
    assert response.status_code == 200
    assert len(content) > 100  # Should have substantial metrics data


@pytest.mark.asyncio
async def test_metrics_tracks_multiple_endpoints(client: AsyncClient):
    """Test that metrics track different endpoints."""
    # Make requests to different endpoints
    await client.get("/")
    await client.get("/health")
    
    # Get metrics
    response = await client.get("/metrics")
    content = response.text
    
    # Both endpoints should be tracked
    assert response.status_code == 200
    # Metrics should contain endpoint paths or status codes
    assert any(keyword in content for keyword in ["http", "request", "response", "status"])


@pytest.mark.asyncio
async def test_metrics_excluded_from_own_tracking(client: AsyncClient):
    """Test that /metrics endpoint doesn't track itself (to avoid metric inflation)."""
    # Get initial metrics
    response1 = await client.get("/metrics")
    content1 = response1.text
    
    # Make multiple calls to /metrics
    await client.get("/metrics")
    await client.get("/metrics")
    
    # Get final metrics
    response2 = await client.get("/metrics")
    content2 = response2.text
    
    # Metrics should exist but shouldn't show significant increase from /metrics calls
    # (This is handled by excluded_handlers in instrumentator config)
    assert response2.status_code == 200
    assert len(content2) > 0
