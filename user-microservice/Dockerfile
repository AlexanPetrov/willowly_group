# Use Python 3.12 slim image
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    psycopg2-binary \
    alembic \
    pydantic[email] \
    pydantic-settings \
    python-jose[cryptography] \
    passlib[bcrypt] \
    python-multipart \
    slowapi \
    redis \
    prometheus-fastapi-instrumentator \
    pytest \
    pytest-asyncio \
    httpx

# Copy application code
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY tests/ /app/tests/
COPY pyproject.toml /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
