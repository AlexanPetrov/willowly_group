"""Tests for memory optimization utilities."""

from app.memory import (
    MemoryEstimate,
    estimate_chunk_memory,
    calculate_adaptive_batch_size,
    MemoryMonitor,
)


def test_estimate_chunk_memory():
    """Test chunk memory estimation."""
    small_chunk = "hello world"
    large_chunk = "x" * 10000
    
    small_estimate = estimate_chunk_memory(small_chunk)
    large_estimate = estimate_chunk_memory(large_chunk)
    
    # Larger chunk should have higher memory estimate
    assert large_estimate > small_estimate
    assert small_estimate > 0
    assert large_estimate > 0


def test_memory_estimate_dataclass():
    """Test MemoryEstimate dataclass."""
    estimate = MemoryEstimate(batch_size=64, avg_chunk_size=2000, estimated_mb=0.5)
    
    assert estimate.batch_size == 64
    assert estimate.avg_chunk_size == 2000
    assert estimate.estimated_mb == 0.5
    
    # Should have string representation
    str_repr = str(estimate)
    assert "batch_size" in str_repr
    assert "2000" in str_repr


def test_calculate_adaptive_batch_size_default():
    """Test adaptive batch size calculation with default memory target."""
    # Assume avg chunk is 2000 bytes
    result = calculate_adaptive_batch_size(avg_chunk_size=2000)
    
    assert result.batch_size > 0
    assert result.avg_chunk_size == 2000
    assert result.estimated_mb > 0


def test_calculate_adaptive_batch_size_small_chunks():
    """Test adaptive batch size with small chunks."""
    # Small chunks should allow larger batch sizes
    small_result = calculate_adaptive_batch_size(avg_chunk_size=500)
    large_result = calculate_adaptive_batch_size(avg_chunk_size=5000)
    
    # Smaller chunks should have larger batch size (or same if hitting max)
    assert small_result.batch_size >= large_result.batch_size


def test_calculate_adaptive_batch_size_custom_memory():
    """Test adaptive batch size with custom memory target."""
    result = calculate_adaptive_batch_size(
        avg_chunk_size=2000,
        target_memory_mb=50,
    )
    
    assert result.batch_size > 0
    assert result.estimated_mb <= 50 * 1.1  # Allow 10% overhead


def test_memory_monitor_record_chunk():
    """Test MemoryMonitor chunk recording."""
    monitor = MemoryMonitor(target_memory_mb=100)
    
    # Record some chunks
    monitor.record_chunk(1000)
    monitor.record_chunk(2000)
    monitor.record_chunk(1500)
    
    assert monitor.chunks_processed == 3
    assert monitor.total_bytes == 4500
    assert monitor.get_current_mb() > 0


def test_memory_monitor_average_chunk_size():
    """Test MemoryMonitor average chunk size calculation."""
    monitor = MemoryMonitor()
    
    monitor.record_chunk(1000)
    monitor.record_chunk(3000)
    
    avg = monitor.get_avg_chunk_size()
    assert avg == 2000  # (1000 + 3000) / 2


def test_memory_monitor_max_tracking():
    """Test MemoryMonitor peak memory tracking."""
    monitor = MemoryMonitor()
    
    monitor.record_chunk(1000)
    monitor.record_chunk(5000)
    monitor.record_chunk(2000)
    
    assert monitor.max_memory_mb > 0
    # Peak memory should be tracked during processing
    assert monitor.max_memory_mb >= monitor.get_current_mb()


def test_memory_monitor_reset():
    """Test MemoryMonitor reset functionality."""
    monitor = MemoryMonitor()
    
    monitor.record_chunk(5000)
    assert monitor.chunks_processed == 1
    
    monitor.reset()
    assert monitor.chunks_processed == 0
    assert monitor.total_bytes == 0
    assert monitor.get_current_mb() == 0


def test_memory_monitor_string_representation():
    """Test MemoryMonitor string representation."""
    monitor = MemoryMonitor()
    monitor.record_chunk(2000)
    monitor.record_chunk(3000)
    
    str_repr = str(monitor)
    assert "Memory:" in str_repr
    assert "Chunks:" in str_repr
    assert "Avg size:" in str_repr


def test_memory_monitor_with_zero_chunks():
    """Test MemoryMonitor with no chunks recorded."""
    monitor = MemoryMonitor()
    
    assert monitor.get_avg_chunk_size() == 0
    assert monitor.get_current_mb() == 0
    assert monitor.chunks_processed == 0


def test_memory_estimate_constraints():
    """Test adaptive batch sizing respects min/max constraints."""
    # Very large chunk should not result in batch size of 0
    result = calculate_adaptive_batch_size(avg_chunk_size=50_000_000)
    assert result.batch_size >= 1
    
    # Very small chunk should not exceed reasonable max
    result = calculate_adaptive_batch_size(avg_chunk_size=100)
    assert result.batch_size <= 512  # Reasonable upper limit
