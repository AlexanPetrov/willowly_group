"""Pytest configuration and shared fixtures for RAG microservice testing."""

import os
from datetime import datetime, timedelta, timezone

# Set TEST_MODE before any app imports
os.environ["TEST_MODE"] = "1"
os.environ["ENABLE_METRICS"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"  # Reduce noise in test output

# Mock configuration for testing
os.environ["SECRET_KEY"] = "test-secret-key-minimum-32-characters-long"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-minimum-32-chars"
os.environ["CHROMA_PATH"] = "/tmp/test_chroma_db"
os.environ["CHROMA_COLLECTION_NAME"] = "test_collection"
os.environ["GEN_MODEL"] = "llama3.1:8b"
os.environ["OLLAMA_HOST"] = "http://localhost:11434"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app


@pytest_asyncio.fixture
async def client():
    """Create an async HTTP client for testing the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def valid_token():
    """Generate a valid JWT access token for testing."""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


@pytest.fixture
def expired_token():
    """Generate an expired JWT token for testing."""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1)
    }
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


@pytest.fixture
def token_missing_sub():
    """Generate a JWT token without 'sub' claim for testing."""
    payload = {
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


@pytest.fixture
def sample_query_request():
    """Sample query request payload."""
    return {
        "text": "What is the capital of France?",
        "k": 3,
        "min_similarity": 0.7
    }


@pytest.fixture
def sample_documents():
    """Sample documents for testing retrieval."""
    return [
        {
            "id": "doc1",
            "content": "Paris is the capital and largest city of France.",
            "metadata": {"source": "geography.txt", "page": 1}
        },
        {
            "id": "doc2",
            "content": "The city of Paris is located on the Seine River.",
            "metadata": {"source": "geography.txt", "page": 2}
        },
        {
            "id": "doc3",
            "content": "France is a country in Western Europe.",
            "metadata": {"source": "geography.txt", "page": 3}
        }
    ]


@pytest.fixture
def sample_retrieval_results():
    """Sample ChromaDB retrieval results."""
    return {
        "ids": [["doc1", "doc2"]],
        "documents": [[
            "Paris is the capital and largest city of France.",
            "The city of Paris is located on the Seine River."
        ]],
        "metadatas": [[
            {"source": "geography.txt", "page": 1},
            {"source": "geography.txt", "page": 2}
        ]],
        "distances": [[0.15, 0.25]]
    }
