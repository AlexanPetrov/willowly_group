"""Tests for app/metrics.py metrics collection."""

from app.metrics import MetricsCollector, OperationMetrics, PipelineMetrics


class TestOperationMetrics:
    """Tests for OperationMetrics dataclass."""

    def test_operation_metrics_initialization(self):
        """OperationMetrics should initialize with operation name."""
        metrics = OperationMetrics("test_operation")
        assert metrics.operation_name == "test_operation"
        assert metrics.duration_seconds == 0.0
        assert metrics.error is None

    def test_operation_metrics_finish(self):
        """Finishing operation should calculate duration."""
        metrics = OperationMetrics("test_operation")
        metrics.finish()
        assert metrics.end_time is not None
        assert metrics.duration_seconds > 0.0

    def test_operation_metrics_finish_with_error(self):
        """Finishing operation with error should record error."""
        metrics = OperationMetrics("test_operation")
        error_msg = "Test error"
        metrics.finish(error=error_msg)
        assert metrics.error == error_msg
        assert metrics.end_time is not None


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_initialization(self):
        """Collector should initialize with empty metrics."""
        collector = MetricsCollector()
        assert collector.extraction_errors == 0
        assert collector.chunking_errors == 0
        assert len(collector.extraction_durations) == 0

    def test_record_extraction(self):
        """Collector should record extraction metrics."""
        collector = MetricsCollector()
        collector.record_extraction(1.5)
        assert len(collector.extraction_durations) == 1
        assert collector.extraction_durations[0] == 1.5
        assert collector.extraction_errors == 0

    def test_record_extraction_with_error(self):
        """Collector should track extraction errors."""
        collector = MetricsCollector()
        collector.record_extraction(1.5, error=True)
        assert collector.extraction_errors == 1

    def test_record_chunking(self):
        """Collector should record chunking metrics."""
        collector = MetricsCollector()
        collector.record_chunking(0.5)
        assert len(collector.chunking_durations) == 1
        assert collector.chunking_errors == 0

    def test_record_embedding(self):
        """Collector should record embedding metrics."""
        collector = MetricsCollector()
        collector.record_embedding(2.0)
        assert len(collector.embedding_durations) == 1

    def test_record_upsert(self):
        """Collector should record upsert metrics."""
        collector = MetricsCollector()
        collector.record_upsert(0.8)
        assert len(collector.upsert_durations) == 1

    def test_calculate_percentile(self):
        """Collector should calculate percentiles correctly."""
        collector = MetricsCollector()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        p50 = collector._calculate_percentile(values, 50)
        assert p50 > 0

    def test_calculate_percentile_empty(self):
        """Percentile of empty list should be 0."""
        collector = MetricsCollector()
        p50 = collector._calculate_percentile([], 50)
        assert p50 == 0.0

    def test_finalize_basic(self):
        """Finalize should calculate pipeline metrics."""
        collector = MetricsCollector()
        collector.record_extraction(1.0)
        collector.record_chunking(0.5)
        collector.record_embedding(1.5)
        collector.record_upsert(0.5)
        
        metrics = collector.finalize(
            total_duration_seconds=5.0,
            files_processed=10,
            total_chunks=100,
        )
        
        assert metrics.total_duration_seconds == 5.0
        assert metrics.files_per_second == 2.0
        assert metrics.chunks_per_second == 20.0

    def test_finalize_with_errors(self):
        """Finalize should track all errors."""
        collector = MetricsCollector()
        collector.record_extraction(1.0, error=True)
        collector.record_chunking(0.5, error=True)
        collector.record_embedding(1.5)
        collector.record_upsert(0.5, error=True)
        
        metrics = collector.finalize(
            total_duration_seconds=5.0,
            files_processed=10,
            total_chunks=100,
        )
        
        assert metrics.extraction_errors == 1
        assert metrics.chunking_errors == 1
        assert metrics.upsert_errors == 1
        assert metrics.embedding_errors == 0
        assert metrics.total_errors == 3

    def test_finalize_latency_percentiles(self):
        """Finalize should calculate latency percentiles."""
        collector = MetricsCollector()
        for i in range(100):
            collector.record_extraction(float(i) / 1000)
        
        metrics = collector.finalize(
            total_duration_seconds=5.0,
            files_processed=10,
            total_chunks=100,
        )
        
        assert metrics.extraction_p50_ms > 0
        assert metrics.extraction_p95_ms >= metrics.extraction_p50_ms
        assert metrics.extraction_p99_ms >= metrics.extraction_p95_ms

    def test_finalize_bytes_per_second(self):
        """Finalize should calculate bytes per second."""
        collector = MetricsCollector()
        metrics = collector.finalize(
            total_duration_seconds=10.0,
            files_processed=5,
            total_chunks=50,
            total_bytes=1000,
        )
        
        assert metrics.bytes_per_second == 100.0


class TestPipelineMetrics:
    """Tests for PipelineMetrics."""

    def test_pipeline_metrics_initialization(self):
        """PipelineMetrics should initialize with zero values."""
        metrics = PipelineMetrics()
        assert metrics.total_duration_seconds == 0.0
        assert metrics.total_errors == 0
        assert metrics.files_per_second == 0.0

    def test_pipeline_metrics_to_dict(self):
        """PipelineMetrics should convert to dictionary."""
        metrics = PipelineMetrics(
            total_duration_seconds=5.0,
            files_per_second=2.0,
            chunks_per_second=20.0,
            total_errors=1,
        )
        
        metrics_dict = metrics.to_dict()
        assert "timing" in metrics_dict
        assert "throughput" in metrics_dict
        assert "errors" in metrics_dict
        assert "latency_percentiles_ms" in metrics_dict
        
        assert metrics_dict["throughput"]["files_per_second"] == 2.0
        assert metrics_dict["throughput"]["chunks_per_second"] == 20.0
        assert metrics_dict["errors"]["total"] == 1

    def test_pipeline_metrics_str(self):
        """PipelineMetrics should have readable string representation."""
        metrics = PipelineMetrics(
            total_duration_seconds=10.0,
            files_per_second=1.0,
            chunks_per_second=10.0,
            extraction_time_seconds=3.0,
            chunking_time_seconds=2.0,
            embedding_time_seconds=3.0,
            upsert_time_seconds=2.0,
        )
        
        metrics_str = str(metrics)
        assert "Throughput:" in metrics_str
        assert "files/s" in metrics_str
        assert "chunks/s" in metrics_str
        assert "Errors:" in metrics_str
        assert "Time:" in metrics_str
