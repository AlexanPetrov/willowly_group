"""Memory optimization utilities for efficient batch processing."""

from dataclasses import dataclass
from typing import Optional

from config import settings
from app.logger import logger


@dataclass(slots=True)
class MemoryEstimate:
    """Memory estimation for batch processing."""
    batch_size: int
    avg_chunk_size: int
    estimated_mb: float
    
    def __str__(self) -> str:
        return f"batch_size={self.batch_size}, avg_chunk={self.avg_chunk_size}B, ~{self.estimated_mb:.1f}MB"


def estimate_chunk_memory(chunk_text: str) -> int:
    """Estimate memory used by a chunk in bytes.
    
    Includes:
    - Text content (UTF-8 encoded)
    - Metadata overhead
    - Python object overhead
    
    Args:
        chunk_text: The chunk content
        
    Returns:
        Estimated memory in bytes
    """
    # UTF-8 encoded text + metadata dict + list overhead
    text_bytes = len(chunk_text.encode("utf-8"))
    metadata_bytes = 512  # Estimated: source_file, chunk_index, chunk_hash, etc.
    python_overhead = 256  # Python object overhead
    
    return text_bytes + metadata_bytes + python_overhead


def calculate_adaptive_batch_size(
    avg_chunk_size: int,
    target_memory_mb: Optional[int] = None,
) -> MemoryEstimate:
    """Calculate optimal batch size based on available memory and chunk size.
    
    Adjusts batch size to keep memory usage within target limits while
    maintaining reasonable throughput.
    
    Args:
        avg_chunk_size: Average chunk size in bytes
        target_memory_mb: Target memory buffer (default from config)
        
    Returns:
        MemoryEstimate with recommended batch size
    """
    if target_memory_mb is None:
        target_memory_mb = settings.MEMORY_BUFFER_MB
    
    # Bytes per chunk (includes overhead)
    bytes_per_chunk = avg_chunk_size * 1.2  # 20% overhead factor
    
    # Calculate batch size to stay within target memory
    target_bytes = target_memory_mb * 1024 * 1024
    calculated_batch = max(1, int(target_bytes / bytes_per_chunk))
    
    # Apply constraints
    min_batch = 1
    max_batch = settings.INGEST_BATCH_SIZE * 4
    optimal_batch = min(max(calculated_batch, min_batch), max_batch)
    
    # Estimate actual memory usage
    estimated_mb = (optimal_batch * bytes_per_chunk) / (1024 * 1024)
    
    logger.debug(
        f"Adaptive batch size: {calculated_batch} → {optimal_batch} "
        f"(memory: {estimated_mb:.1f}MB, target: {target_memory_mb}MB)"
    )
    
    return MemoryEstimate(
        batch_size=optimal_batch,
        avg_chunk_size=avg_chunk_size,
        estimated_mb=estimated_mb,
    )


class MemoryMonitor:
    """Monitor memory usage during batch processing.
    
    Tracks memory consumption and warns if thresholds are exceeded.
    """
    
    def __init__(self, target_memory_mb: Optional[int] = None):
        """Initialize memory monitor.
        
        Args:
            target_memory_mb: Target memory limit in MB
        """
        self.target_memory_mb = target_memory_mb or settings.MEMORY_BUFFER_MB
        self.max_memory_mb = 0.0
        self.chunks_processed = 0
        self.total_bytes = 0
    
    def record_chunk(self, chunk_size: int) -> None:
        """Record memory usage for a chunk.
        
        Args:
            chunk_size: Chunk size in bytes
        """
        self.total_bytes += chunk_size
        current_mb = self.total_bytes / (1024 * 1024)
        
        if current_mb > self.max_memory_mb:
            self.max_memory_mb = current_mb
        
        self.chunks_processed += 1
        
        # Warn if approaching limit
        if current_mb > self.target_memory_mb * 0.9:
            logger.warning(
                f"Memory usage high: {current_mb:.1f}MB / {self.target_memory_mb}MB "
                f"({self.chunks_processed} chunks)"
            )
    
    def reset(self) -> None:
        """Reset memory tracking."""
        self.total_bytes = 0
        self.chunks_processed = 0
    
    def get_current_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.total_bytes / (1024 * 1024)
    
    def get_avg_chunk_size(self) -> int:
        """Get average chunk size in bytes."""
        if self.chunks_processed == 0:
            return 0
        return self.total_bytes // self.chunks_processed
    
    def __str__(self) -> str:
        avg_size = self.get_avg_chunk_size()
        current_mb = self.get_current_mb()
        return (
            f"Memory: {current_mb:.1f}MB (peak {self.max_memory_mb:.1f}MB), "
            f"Chunks: {self.chunks_processed}, "
            f"Avg size: {avg_size}B"
        )
