"""Metrics collection and reporting for ingestion pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


@dataclass(slots=True)
class OperationMetrics:
    """Metrics for a single operation."""
    operation_name: str
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    
    def finish(self, error: str | None = None) -> None:
        """Mark operation as finished."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.error = error


@dataclass(slots=True)
class PipelineMetrics:
    """Comprehensive metrics for pipeline execution."""
    
    # Timing
    total_duration_seconds: float = 0.0
    extraction_time_seconds: float = 0.0
    chunking_time_seconds: float = 0.0
    embedding_time_seconds: float = 0.0
    upsert_time_seconds: float = 0.0
    
    # Throughput
    files_per_second: float = 0.0
    chunks_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # Errors
    extraction_errors: int = 0
    chunking_errors: int = 0
    embedding_errors: int = 0
    upsert_errors: int = 0
    total_errors: int = 0
    
    # Latency percentiles (in milliseconds)
    extraction_p50_ms: float = 0.0
    extraction_p95_ms: float = 0.0
    extraction_p99_ms: float = 0.0
    
    chunking_p50_ms: float = 0.0
    chunking_p95_ms: float = 0.0
    chunking_p99_ms: float = 0.0
    
    embedding_p50_ms: float = 0.0
    embedding_p95_ms: float = 0.0
    embedding_p99_ms: float = 0.0
    
    upsert_p50_ms: float = 0.0
    upsert_p95_ms: float = 0.0
    upsert_p99_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "timing": {
                "total_duration_seconds": round(self.total_duration_seconds, 3),
                "extraction_seconds": round(self.extraction_time_seconds, 3),
                "chunking_seconds": round(self.chunking_time_seconds, 3),
                "embedding_seconds": round(self.embedding_time_seconds, 3),
                "upsert_seconds": round(self.upsert_time_seconds, 3),
            },
            "throughput": {
                "files_per_second": round(self.files_per_second, 2),
                "chunks_per_second": round(self.chunks_per_second, 2),
                "bytes_per_second": round(self.bytes_per_second, 2),
            },
            "errors": {
                "extraction": self.extraction_errors,
                "chunking": self.chunking_errors,
                "embedding": self.embedding_errors,
                "upsert": self.upsert_errors,
                "total": self.total_errors,
            },
            "latency_percentiles_ms": {
                "extraction": {
                    "p50": round(self.extraction_p50_ms, 2),
                    "p95": round(self.extraction_p95_ms, 2),
                    "p99": round(self.extraction_p99_ms, 2),
                },
                "chunking": {
                    "p50": round(self.chunking_p50_ms, 2),
                    "p95": round(self.chunking_p95_ms, 2),
                    "p99": round(self.chunking_p99_ms, 2),
                },
                "embedding": {
                    "p50": round(self.embedding_p50_ms, 2),
                    "p95": round(self.embedding_p95_ms, 2),
                    "p99": round(self.embedding_p99_ms, 2),
                },
                "upsert": {
                    "p50": round(self.upsert_p50_ms, 2),
                    "p95": round(self.upsert_p95_ms, 2),
                    "p99": round(self.upsert_p99_ms, 2),
                },
            },
        }
    
    def __str__(self) -> str:
        """Formatted metrics summary."""
        return (
            f"Throughput: {self.files_per_second:.2f} files/s, {self.chunks_per_second:.2f} chunks/s | "
            f"Errors: {self.total_errors} total | "
            f"Time: {self.total_duration_seconds:.2f}s (extraction: {self.extraction_time_seconds:.2f}s, "
            f"chunking: {self.chunking_time_seconds:.2f}s, embedding: {self.embedding_time_seconds:.2f}s, "
            f"upsert: {self.upsert_time_seconds:.2f}s)"
        )


class MetricsCollector:
    """Collect and calculate metrics during pipeline execution."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.extraction_durations: List[float] = []
        self.chunking_durations: List[float] = []
        self.embedding_durations: List[float] = []
        self.upsert_durations: List[float] = []
        
        self.extraction_errors = 0
        self.chunking_errors = 0
        self.embedding_errors = 0
        self.upsert_errors = 0
    
    def record_extraction(self, duration_seconds: float, error: bool = False) -> None:
        """Record extraction operation timing."""
        self.extraction_durations.append(duration_seconds)
        if error:
            self.extraction_errors += 1
    
    def record_chunking(self, duration_seconds: float, error: bool = False) -> None:
        """Record chunking operation timing."""
        self.chunking_durations.append(duration_seconds)
        if error:
            self.chunking_errors += 1
    
    def record_embedding(self, duration_seconds: float, error: bool = False) -> None:
        """Record embedding operation timing."""
        self.embedding_durations.append(duration_seconds)
        if error:
            self.embedding_errors += 1
    
    def record_upsert(self, duration_seconds: float, error: bool = False) -> None:
        """Record upsert operation timing."""
        self.upsert_durations.append(duration_seconds)
        if error:
            self.upsert_errors += 1
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile from list of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def finalize(
        self,
        total_duration_seconds: float,
        files_processed: int,
        total_chunks: int,
        total_bytes: int = 0,
    ) -> PipelineMetrics:
        """Calculate final metrics."""
        metrics = PipelineMetrics()
        
        # Timing
        metrics.total_duration_seconds = total_duration_seconds
        metrics.extraction_time_seconds = sum(self.extraction_durations)
        metrics.chunking_time_seconds = sum(self.chunking_durations)
        metrics.embedding_time_seconds = sum(self.embedding_durations)
        metrics.upsert_time_seconds = sum(self.upsert_durations)
        
        # Throughput
        if total_duration_seconds > 0:
            metrics.files_per_second = files_processed / total_duration_seconds
            metrics.chunks_per_second = total_chunks / total_duration_seconds
            if total_bytes > 0:
                metrics.bytes_per_second = total_bytes / total_duration_seconds
        
        # Errors
        metrics.extraction_errors = self.extraction_errors
        metrics.chunking_errors = self.chunking_errors
        metrics.embedding_errors = self.embedding_errors
        metrics.upsert_errors = self.upsert_errors
        metrics.total_errors = (
            self.extraction_errors
            + self.chunking_errors
            + self.embedding_errors
            + self.upsert_errors
        )
        
        # Latency percentiles (convert to milliseconds)
        metrics.extraction_p50_ms = self._calculate_percentile(self.extraction_durations, 50) * 1000
        metrics.extraction_p95_ms = self._calculate_percentile(self.extraction_durations, 95) * 1000
        metrics.extraction_p99_ms = self._calculate_percentile(self.extraction_durations, 99) * 1000
        
        metrics.chunking_p50_ms = self._calculate_percentile(self.chunking_durations, 50) * 1000
        metrics.chunking_p95_ms = self._calculate_percentile(self.chunking_durations, 95) * 1000
        metrics.chunking_p99_ms = self._calculate_percentile(self.chunking_durations, 99) * 1000
        
        metrics.embedding_p50_ms = self._calculate_percentile(self.embedding_durations, 50) * 1000
        metrics.embedding_p95_ms = self._calculate_percentile(self.embedding_durations, 95) * 1000
        metrics.embedding_p99_ms = self._calculate_percentile(self.embedding_durations, 99) * 1000
        
        metrics.upsert_p50_ms = self._calculate_percentile(self.upsert_durations, 50) * 1000
        metrics.upsert_p95_ms = self._calculate_percentile(self.upsert_durations, 95) * 1000
        metrics.upsert_p99_ms = self._calculate_percentile(self.upsert_durations, 99) * 1000
        
        return metrics
