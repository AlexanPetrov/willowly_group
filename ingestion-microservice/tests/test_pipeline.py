"""Tests for app/pipeline.py ingestion pipeline."""

import pytest  # type: ignore

from app.pipeline import IngestionStats, iter_raw_texts


class TestIngestionStats:
    """Tests for IngestionStats dataclass."""

    def test_ingestion_stats_initialization(self):
        """Stats should initialize with correct values."""
        stats = IngestionStats(
            files_processed=5,
            files_failed=0,
            total_chunks=50,
            chunks_added=45,
            chunks_skipped=5,
        )
        assert stats.files_processed == 5
        assert stats.total_chunks == 50
        assert stats.chunks_added == 45
        assert stats.chunks_skipped == 5

    def test_ingestion_stats_zero_values(self):
        """Stats should handle zero values."""
        stats = IngestionStats(
            files_processed=0,
            files_failed=0,
            total_chunks=0,
            chunks_added=0,
            chunks_skipped=0,
        )
        assert stats.files_processed == 0
        assert stats.total_chunks == 0

    def test_ingestion_stats_elapsed_seconds(self):
        """Elapsed time should be calculated correctly."""
        stats = IngestionStats(
            files_processed=1,
            total_chunks=10,
            chunks_added=10,
        )
        elapsed = stats.elapsed_seconds
        assert elapsed >= 0
        assert isinstance(elapsed, float)

    def test_ingestion_stats_chunks_per_second(self):
        """Throughput should be calculated."""
        stats = IngestionStats(
            files_processed=1,
            total_chunks=100,
            chunks_added=100,
        )
        throughput = stats.chunks_per_second
        assert isinstance(throughput, float)

    def test_ingestion_stats_str_repr(self):
        """Stats should have useful string representation."""
        stats = IngestionStats(
            files_processed=2,
            files_failed=0,
            total_chunks=20,
            chunks_added=18,
            chunks_skipped=2,
        )
        stats_str = str(stats)
        assert "Files:" in stats_str
        assert "Chunks:" in stats_str
        assert "Time:" in stats_str


class TestIterRawTexts:
    """Tests for iter_raw_texts async iterator."""

    @pytest.mark.asyncio
    async def test_iter_raw_texts_txt_files(self, temp_dir, sample_txt_content: str):
        """Iterator should find and yield txt files."""
        from unittest.mock import patch
        
        # Create test txt files
        (temp_dir / "txts" / "file1.txt").write_text(sample_txt_content)
        (temp_dir / "txts" / "file2.txt").write_text("Another file")

        # Mock the settings to use temp_dir
        with patch("app.pipeline.settings") as mock_settings:
            mock_settings.get_raw_pdfs_dir.return_value = temp_dir / "pdfs"
            mock_settings.get_raw_txts_dir.return_value = temp_dir / "txts"

            files = []
            async for filename, content in iter_raw_texts():
                files.append((filename, content))

            assert len(files) >= 2
            filenames = [f[0] for f in files]
            assert any("file1.txt" in fn for fn in filenames)
            assert any("file2.txt" in fn for fn in filenames)

    @pytest.mark.asyncio
    async def test_iter_raw_texts_returns_tuples(self, temp_dir, sample_txt_content):
        """Iterator should return (filename, content) tuples."""
        from unittest.mock import patch

        (temp_dir / "txts" / "test.txt").write_text(sample_txt_content)

        with patch("app.pipeline.settings") as mock_settings:
            mock_settings.get_raw_pdfs_dir.return_value = temp_dir / "pdfs"
            mock_settings.get_raw_txts_dir.return_value = temp_dir / "txts"

            async for filename, content in iter_raw_texts():
                assert isinstance(filename, str)
                assert isinstance(content, str)
                assert len(filename) > 0
                assert len(content) > 0
                break  # Just check first result

    @pytest.mark.asyncio
    async def test_iter_raw_texts_empty_directory(self, temp_dir):
        """Iterator should handle empty directory gracefully."""
        from unittest.mock import patch

        with patch("app.pipeline.settings") as mock_settings:
            mock_settings.get_raw_pdfs_dir.return_value = temp_dir / "pdfs"
            mock_settings.get_raw_txts_dir.return_value = temp_dir / "txts"

            files = []
            async for filename, content in iter_raw_texts():
                files.append((filename, content))

            # Should complete without error, may have 0 files
            assert isinstance(files, list)

    @pytest.mark.asyncio
    async def test_iter_raw_texts_content_not_empty(self, temp_dir, sample_txt_content):
        """Iterator should yield actual content."""
        from unittest.mock import patch

        (temp_dir / "txts" / "content_test.txt").write_text(sample_txt_content)

        with patch("app.pipeline.settings") as mock_settings:
            mock_settings.get_raw_pdfs_dir.return_value = temp_dir / "pdfs"
            mock_settings.get_raw_txts_dir.return_value = temp_dir / "txts"

            content_found = False
            async for filename, content in iter_raw_texts():
                if content is not None and "quick" in content:
                    content_found = True
                    break

            assert content_found


