"""Pytest fixtures for ingestion-microservice tests."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # type: ignore

import asyncio
from app.logger import logger
from config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        (temp_path / "pdfs").mkdir()
        (temp_path / "txts").mkdir()
        yield temp_path


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temp directories."""
    return Settings(
        APP_ENV="test",
        RAW_DATA_DIR=temp_dir,
        CHROMA_PATH=temp_dir / "chroma_db",
        LOG_LEVEL="DEBUG",
        LOG_FILE=None,
    )


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Create minimal valid PDF bytes for testing."""
    # Minimal PDF structure (doesn't require any external libs to validate)
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 4 0 R
>>
>>
/MediaBox [0 0 612 792]
/Contents 5 0 R
>>
endobj
4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
5 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000244 00000 n
0000000333 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
427
%%EOF
"""


@pytest.fixture
def sample_txt_content() -> str:
    """Create sample text content for testing."""
    return """This is a test document with multiple paragraphs.

The quick brown fox jumps over the lazy dog.
This is a common pangram used in testing.

Here's another paragraph with some content
that can be used to test chunking and text extraction.

Final paragraph for testing purposes.
"""


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB client and collection."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    
    # Mock collection methods
    mock_collection.upsert = AsyncMock(return_value=None)
    mock_collection.get = MagicMock(return_value={"ids": []})
    mock_collection.delete = AsyncMock(return_value=None)
    
    mock_client.get_collection = MagicMock(return_value=mock_collection)
    mock_client.delete_collection = AsyncMock(return_value=None)
    mock_client.reset = AsyncMock(return_value=None)
    
    return mock_client, mock_collection


@pytest.fixture
def mock_ollama():
    """Mock Ollama embedding client."""
    mock_client = AsyncMock()
    mock_client.embeddings = AsyncMock(
        return_value={
            "embedding": [0.1] * 384  # Typical embedding dimension
        }
    )
    return mock_client


@pytest.fixture
async def mock_chroma_client(mock_chromadb):
    """Fixture for mocked ChromaDB client context."""
    mock_client, mock_collection = mock_chromadb
    
    with patch("app.chroma.chromadb.PersistentClient", return_value=mock_client):
        with patch("app.chroma.embedding_functions.OllamaEmbeddingFunction"):
            yield mock_client, mock_collection


@pytest.fixture
def test_logger():
    """Get test logger."""
    return logger
