###########
# Builder #
###########
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for uv build (kept only in builder)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Fast dependency installer
RUN pip install --no-cache-dir uv

# Copy project metadata first (better layer cache). uv.lock is optional.
COPY pyproject.toml ./
COPY uv.lock ./

# Install runtime and dev deps into system site-packages
RUN uv pip install --system --no-cache-dir . --group dev

# Copy application source
COPY . /app


############
# Runtime  #
############
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages and app code from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "cli.py", "ingest"]
