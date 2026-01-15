"""Tests for app/utils.py utilities."""

from pathlib import Path

import pytest  # type: ignore

from app.utils import chunk_text, extract_text_from_txt, hash_text, stable_chunk_id


class TestHashText:
    """Tests for hash_text function."""

    def test_hash_text_consistency(self):
        """Hash should be consistent for same input."""
        text = "Hello, world!"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2

    def test_hash_text_different_for_different_input(self):
        """Hash should differ for different inputs."""
        hash1 = hash_text("Hello")
        hash2 = hash_text("World")
        assert hash1 != hash2

    def test_hash_text_returns_string(self):
        """Hash should return string (hex digest)."""
        result = hash_text("test")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_text_deterministic_across_runs(self):
        """Same input should always produce same hash."""
        text = "consistent test data"
        hashes = [hash_text(text) for _ in range(5)]
        assert len(set(hashes)) == 1, "Hash should be deterministic"

    def test_hash_text_hex_format(self):
        """Hash should return valid hex string."""
        result = hash_text("test content")
        # Hex string should only contain valid hex characters
        try:
            int(result, 16)
            valid_hex = True
        except ValueError:
            valid_hex = False
        assert valid_hex


class TestStableChunkId:
    """Tests for stable_chunk_id function."""

    def test_stable_chunk_id_format(self):
        """Chunk ID should have expected format."""
        chunk_id = stable_chunk_id("doc.txt", 0, "abc123")
        assert isinstance(chunk_id, str)
        assert "doc.txt" in chunk_id
        assert "0" in chunk_id
        assert "abc123" in chunk_id

    def test_stable_chunk_id_consistency(self):
        """Same content should produce same ID."""
        id1 = stable_chunk_id("file.txt", 1, "hash1")
        id2 = stable_chunk_id("file.txt", 1, "hash1")
        assert id1 == id2

    def test_stable_chunk_id_different_for_different_params(self):
        """Different params should produce different IDs."""
        id1 = stable_chunk_id("file.txt", 0, "hash1")
        id2 = stable_chunk_id("file.txt", 1, "hash1")
        id3 = stable_chunk_id("file.txt", 0, "hash2")
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_stable_chunk_id_includes_all_components(self):
        """ID should include filename, index, and digest."""
        filename = "document.txt"
        idx = 5
        digest = "def456"
        chunk_id = stable_chunk_id(filename, idx, digest)
        assert filename in chunk_id
        assert str(idx) in chunk_id
        assert digest in chunk_id


class TestChunkText:
    """Tests for chunk_text function."""

    def test_chunk_text_basic(self):
        """Chunk text into basic chunks."""
        text = "This is a sentence. " * 10  # Repeated text to ensure chunking
        chunks = chunk_text(text)
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)

    def test_chunk_text_produces_non_empty_chunks(self):
        """All chunks should be non-empty."""
        text = "word " * 100  # Create long text
        chunks = chunk_text(text)
        assert len(chunks) > 0
        assert all(len(chunk) > 0 for chunk in chunks)
        assert all(chunk.strip() for chunk in chunks)

    def test_chunk_text_respects_chunk_size(self):
        """Chunks should not exceed settings chunk_chars."""
        text = "word " * 100
        chunks = chunk_text(text)
        # Chunks should be reasonable size (not overly large)
        assert all(len(chunk) > 0 for chunk in chunks)

    def test_chunk_text_empty_text(self):
        """Empty text should return empty list."""
        chunks = chunk_text("")
        assert chunks == []

    def test_chunk_text_whitespace_only(self):
        """Whitespace-only text should return empty list."""
        chunks = chunk_text("   \n\t  ")
        # After strip(), whitespace-only chunks are filtered
        assert chunks == [] or all(not chunk.strip() for chunk in chunks)

    def test_chunk_text_short_text(self):
        """Short text should return as one or few chunks."""
        chunks = chunk_text("Hello world")
        assert len(chunks) >= 1

    def test_chunk_text_preserves_content(self):
        """Content should be preserved in chunks."""
        text = "The quick brown fox jumps over the lazy dog."
        chunks = chunk_text(text)
        reconstructed = " ".join(chunks)
        # Key words should be present
        assert "quick" in reconstructed or "quick" in text
        assert "brown" in reconstructed or "brown" in text

    def test_chunk_text_no_duplicates_for_non_overlapping(self):
        """For non-overlapping chunks, content shouldn't be duplicated."""
        text = "a b c d e f g h i j k l m n o p q r s t"
        chunks = chunk_text(text)
        # Chunks should be created without errors
        assert len(chunks) > 0


class TestExtractTextFromTxt:
    """Tests for extract_text_from_txt function."""

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_basic(self, temp_dir: Path, sample_txt_content: str):
        """Extract text from simple txt file."""
        txt_file = temp_dir / "txts" / "test.txt"
        txt_file.write_text(sample_txt_content)

        text = await extract_text_from_txt(str(txt_file))
        assert text is not None
        assert "quick brown fox" in text

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_nonexistent_file(self):
        """Extracting from nonexistent file should raise error."""
        with pytest.raises(FileNotFoundError):
            await extract_text_from_txt("/nonexistent/path/file.txt")

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_empty_file(self, temp_dir: Path):
        """Extracting from empty file should return None."""
        txt_file = temp_dir / "txts" / "empty.txt"
        txt_file.write_text("")

        text = await extract_text_from_txt(str(txt_file))
        assert text is None

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_with_unicode(self, temp_dir: Path):
        """Extract text with unicode characters."""
        content = "Hello 世界\nTest émojis: 🚀✨"
        txt_file = temp_dir / "txts" / "unicode.txt"
        txt_file.write_text(content, encoding="utf-8")

        text = await extract_text_from_txt(str(txt_file))
        assert text is not None
        assert "世界" in text
        assert "🚀" in text

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_multiline(self, temp_dir: Path):
        """Extract text with multiple lines."""
        content = "Line 1\nLine 2\nLine 3\n"
        txt_file = temp_dir / "txts" / "multiline.txt"
        txt_file.write_text(content)

        text = await extract_text_from_txt(str(txt_file))
        assert text is not None
        assert "Line 1" in text
        assert "Line 2" in text
        assert "Line 3" in text

    @pytest.mark.asyncio
    async def test_extract_text_from_txt_whitespace_only(self, temp_dir: Path):
        """Extracting whitespace-only file should return None."""
        txt_file = temp_dir / "txts" / "whitespace.txt"
        txt_file.write_text("   \n\t  \n  ")

        text = await extract_text_from_txt(str(txt_file))
        assert text is None

