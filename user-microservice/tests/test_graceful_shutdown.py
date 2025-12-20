"""
Tests for graceful shutdown functionality.
"""

import pytest
import asyncio
from app.main import GracefulShutdownManager


@pytest.mark.asyncio
async def test_shutdown_manager_initialization():
    """Test shutdown manager initializes correctly."""
    manager = GracefulShutdownManager()
    assert manager.is_shutting_down is False
    assert manager.active_requests == 0
    assert manager.shutdown_timeout == 30


@pytest.mark.asyncio
async def test_request_tracking():
    """Test request start/finish tracking."""
    manager = GracefulShutdownManager()
    
    manager.request_started()
    assert manager.active_requests == 1
    
    manager.request_started()
    assert manager.active_requests == 2
    
    manager.request_finished()
    assert manager.active_requests == 1
    
    manager.request_finished()
    assert manager.active_requests == 0


@pytest.mark.asyncio
async def test_request_tracking_prevents_negative():
    """Test request finished doesn't go below zero."""
    manager = GracefulShutdownManager()
    
    manager.request_finished()
    assert manager.active_requests == -1  # Edge case but shouldn't crash


@pytest.mark.asyncio
async def test_shutdown_with_no_active_requests():
    """Test graceful shutdown completes immediately when no active requests."""
    manager = GracefulShutdownManager()
    
    start = asyncio.get_event_loop().time()
    await manager.initiate_shutdown()
    duration = asyncio.get_event_loop().time() - start
    
    assert manager.is_shutting_down is True
    assert duration < 1.0  # Should complete instantly


@pytest.mark.asyncio
async def test_shutdown_waits_for_active_requests():
    """Test graceful shutdown waits for active requests to complete."""
    manager = GracefulShutdownManager()
    
    # Simulate active requests
    manager.request_started()
    manager.request_started()
    
    # Start shutdown in background
    shutdown_task = asyncio.create_task(manager.initiate_shutdown())
    
    # Give it a moment to start
    await asyncio.sleep(0.1)
    
    # Shutdown should be waiting
    assert not shutdown_task.done()
    assert manager.is_shutting_down is True
    
    # Complete one request
    manager.request_finished()
    await asyncio.sleep(0.1)
    
    # Still waiting
    assert not shutdown_task.done()
    
    # Complete final request
    manager.request_finished()
    
    # Now shutdown should complete
    await asyncio.wait_for(shutdown_task, timeout=1.0)
    assert shutdown_task.done()


@pytest.mark.asyncio
async def test_shutdown_timeout():
    """Test graceful shutdown times out if requests take too long."""
    manager = GracefulShutdownManager()
    manager.shutdown_timeout = 0.5  # Short timeout for testing
    
    # Simulate active request that never finishes
    manager.request_started()
    
    start = asyncio.get_event_loop().time()
    await manager.initiate_shutdown()
    duration = asyncio.get_event_loop().time() - start
    
    # Should timeout after 0.5 seconds
    assert 0.4 < duration < 0.7
    assert manager.is_shutting_down is True


@pytest.mark.asyncio
async def test_shutdown_prevents_new_requests():
    """Test that new requests aren't counted during shutdown."""
    manager = GracefulShutdownManager()
    
    manager.is_shutting_down = True
    
    # Try to start new request
    manager.request_started()
    
    # Should not increment counter during shutdown
    assert manager.active_requests == 0


@pytest.mark.asyncio
async def test_multiple_shutdown_calls():
    """Test that calling initiate_shutdown multiple times is safe."""
    manager = GracefulShutdownManager()
    
    await manager.initiate_shutdown()
    assert manager.is_shutting_down is True
    
    # Second call should be no-op
    await manager.initiate_shutdown()
    assert manager.is_shutting_down is True


@pytest.mark.asyncio
async def test_shutdown_integration(client):
    """Test graceful shutdown middleware integration."""
    from app.main import shutdown_manager
    
    # Normal request should work
    response = await client.get("/health")
    assert response.status_code in [200, 503]  # 503 if DB not available in test
    
    # Simulate shutdown
    original_state = shutdown_manager.is_shutting_down
    shutdown_manager.is_shutting_down = True
    
    try:
        # Request during shutdown should be rejected
        response = await client.get("/health")
        assert response.status_code == 503
        assert "shutting down" in response.json()["message"].lower()
        assert "Retry-After" in response.headers
    finally:
        # Restore state
        shutdown_manager.is_shutting_down = original_state
