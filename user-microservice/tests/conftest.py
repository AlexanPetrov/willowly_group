"""
Pytest configuration and shared fixtures for testing.
Sets up test database and test client.
"""

import os

# Set TEST_MODE before any app imports to disable rate limiting
os.environ["TEST_MODE"] = "1"

# Enable metrics endpoint for testing
os.environ["ENABLE_METRICS"] = "true"

# Detect Docker BEFORE any app imports. Default to Docker host when SKIP_ENV_FILE is set.
db_host_env = os.getenv("TEST_DB_HOST")
DB_HOST = db_host_env if db_host_env else ("db" if os.getenv("SKIP_ENV_FILE") else "localhost")
TEST_DB_URL = f"postgresql+asyncpg://api_user:pass123@{DB_HOST}/user_microservice_test_db"

# Ensure app config uses the test database before importing app modules
os.environ["DB_URL"] = TEST_DB_URL
os.environ.setdefault("APP_ENV", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.main import app
from app.db import Base
from app import db as app_db
from app.cache import cache_manager

# Connect to Redis cache once at module import
import asyncio
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_loop.run_until_complete(cache_manager.connect())


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine with proper async configuration."""
    # Create test engine with NullPool to avoid connection pooling issues
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=NullPool,  # Avoid connection pooling in tests
        connect_args={
            "server_settings": {"jit": "off"}  # Disable JIT for test stability
        }
    )
    
    # Create test session maker
    test_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Store original session maker and override it BEFORE creating tables
    original_session = app_db.async_session
    app_db.async_session = test_session_maker
    
    # Create all tables using SQLAlchemy (tests use direct creation for speed)
    # Note: Production uses Alembic migrations instead
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Restore original session maker
    app_db.async_session = original_session
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db_engine):
    """Create a test HTTP client with overridden database."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0  # Increase timeout for test stability
    ) as ac:
        yield ac


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "password123"
    }


@pytest.fixture
def sample_users():
    """Multiple sample users for batch testing."""
    return [
        {"name": "Alice", "email": "alice@example.com", "password": "password123"},
        {"name": "Bob", "email": "bob@example.com", "password": "password123"},
        {"name": "Charlie", "email": "charlie@example.com", "password": "password123"},
        {"name": "Diana", "email": "diana@example.com", "password": "password123"},
        {"name": "Eve", "email": "eve@example.com", "password": "password123"},
    ]
