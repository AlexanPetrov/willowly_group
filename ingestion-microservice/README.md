# Ingestion Microservice

Async document ingestion pipeline for processing PDFs and text files into a ChromaDB vector database with semantic embeddings via Ollama.

## ✨ Features

- **FastAPI REST endpoints**: Upload documents and track processing status
- **JWT authentication**: Secure token-based auth (matches User/RAG services)
- **Async processing**: Celery + Redis for background job queue
- **User isolation**: Documents stored per user_id from JWT token
- **Multi-format support**: PDFs and TXT files
- **Smart chunking**: Configurable text chunking with overlap for better retrieval
- **Deduplication**: Stable IDs via xxhash/MD5 hashing
- **Vector embeddings**: Ollama integration for semantic embeddings
- **ChromaDB storage**: Vector database with idempotent upserts
- **Memory optimization**: Stream processing, adaptive batch sizing, memory monitoring
- **Comprehensive metrics**: Track throughput, latency, and errors
- **Full test coverage**: pytest tests with auth validation
- **Configuration management**: Pydantic v2 with field validation
- **Docker ready**: Multi-stage Docker build with Redis and Celery

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Ollama running locally or remotely
- `uv` package manager

### Installation

```bash
# Clone repository
cd ingestion-microservice

# Setup environment variables
cp .env.example .env
# Edit .env and set your JWT_SECRET_KEY (must match User/RAG services)

# Install dependencies
make install

# Run tests
make test
```

> **Important**: The `JWT_SECRET_KEY` in `.env` must match the key used in User and RAG microservices for authentication to work.

### Run Ingestion

```bash
# Process documents
make ingest

# Development mode (auto-reload)
make dev

# Check configuration
make config

# Health check
make health
```

### API Usage (FastAPI)

**Start services:**
```bash
# Terminal 1: Start Celery worker
make dev-worker

# Terminal 2: Start FastAPI server
make dev-api
```

**Upload a document:**
```bash
curl -X POST http://127.0.0.1:8003/v1/ingest \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.txt"

# Response:
# {
#   "task_id": "f3390d6a-179a-488a-a30a-f85318af654f",
#   "status": "processing",
#   "message": "Document 'document.txt' queued for processing"
# }
```

**Check processing status:**
```bash
curl http://127.0.0.1:8003/v1/ingest/status/f3390d6a-179a-488a-a30a-f85318af654f \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response shows: status = "processing" | "completed" | "failed"
```

**Health check:**
```bash
curl http://127.0.0.1:8003/health
```

**Authentication:**
- Requires valid JWT token from User Microservice
- Token must match `JWT_SECRET_KEY` in `.env` file
- Token `sub` claim becomes `user_id` for document isolation

## � API Endpoints

### POST /v1/ingest
Upload a document for async processing.

**Request:**
```bash
curl -X POST http://localhost:8003/v1/ingest \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf"
```

**Response (202 Accepted):**
```json
{
  "task_id": "f3390d6a-179a-488a-a30a-f85318af654f",
  "status": "processing",
  "message": "Document 'document.pdf' queued for processing"
}
```

**Errors:**
- `401 Unauthorized`: Missing or invalid JWT token
- `422 Unprocessable Entity`: No file provided

### GET /v1/ingest/status/{task_id}
Check the processing status of an uploaded document.

**Request:**
```bash
curl http://localhost:8003/v1/ingest/status/f3390d6a-179a-488a-a30a-f85318af654f \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK) - Processing:**
```json
{
  "task_id": "f3390d6a-179a-488a-a30a-f85318af654f",
  "status": "processing",
  "message": "Document is being processed"
}
```

**Response (200 OK) - Completed:**
```json
{
  "task_id": "f3390d6a-179a-488a-a30a-f85318af654f",
  "status": "completed",
  "message": "Ingestion completed successfully",
  "result": {
    "success": true,
    "user_id": "8",
    "filename": "document.pdf",
    "file_path": "../data/raw/8/pdfs/document.pdf",
    "files_processed": 1,
    "files_failed": 0,
    "chunks_total": 42,
    "chunks_added": 40,
    "chunks_skipped": 2,
    "elapsed_seconds": 3.42,
    "throughput_chunks_per_sec": 12.28
  }
}
```

**Response (200 OK) - Failed:**
```json
{
  "task_id": "f3390d6a-179a-488a-a30a-f85318af654f",
  "status": "failed",
  "message": "Ingestion failed: Error extracting PDF",
  "result": null
}
```

### GET /health
Health check endpoint (no authentication required).

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "dev"
}
```

## �📁 Project Structure

```
ingestion-microservice/
├── app/
│   ├── __init__.py
│   ├── auth.py             # JWT token validation
│   ├── chroma.py           # ChromaDB client wrapper
│   ├── logger.py           # Logging configuration
│   ├── main.py             # FastAPI application and routes
│   ├── memory.py           # Memory optimization and monitoring
│   ├── metrics.py          # Metrics collection system
│   ├── pipeline.py         # Main ingestion pipeline
│   ├── retry.py            # Retry logic for async operations
│   ├── schemas.py          # Pydantic request/response models
│   ├── tasks.py            # Celery background tasks
│   └── utils.py            # Text extraction, chunking, hashing
├── tests/
│   ├── conftest.py         # Pytest fixtures
│   ├── test_api.py         # FastAPI endpoint tests
│   ├── test_chroma.py      # ChromaDB tests
│   ├── test_config.py      # Configuration validation tests
│   ├── test_memory.py      # Memory optimization tests
│   ├── test_metrics.py     # Metrics collection tests
│   ├── test_pipeline.py    # Pipeline integration tests
│   └── test_utils.py       # Utility function tests
├── examples/
│   └── metrics_example.py  # Metrics usage example
├── cli.py                  # Typer CLI interface (legacy)
├── config.py               # Pydantic settings with validation
├── __main__.py             # Entry point
├── .env                    # Environment variables (copy .env.example)
├── Dockerfile              # Container image
├── docker-compose.yml      # Local development stack (Ollama, Redis, API, Celery)
├── pyproject.toml          # uv dependencies and pytest config
├── pyrightconfig.json      # Pyright type checking config
└── Makefile                # Task automation
```

## ⚙️ Configuration

Configuration is managed via Pydantic v2 with automatic environment variable loading.

### Core Settings

```python
from config import Settings

settings = Settings()
print(f"App environment: {settings.APP_ENV}")
print(f"Ollama endpoint: {settings.OLLAMA_HOST}")
print(f"Embedding model: {settings.EMB_MODEL}")
print(f"ChromaDB path: {settings.CHROMA_PATH}")
```

### Environment Variables

```bash
# Application
APP_ENV=dev                           # dev, test, prod
APP_NAME=Ingestion Microservice

# JWT Authentication (required, from User Microservice)
JWT_SECRET_KEY=your-secret-key-here  # Must match User/RAG services (32+ chars)
JWT_ALGORITHM=HS256

# Redis & Celery
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1

# FastAPI
API_HOST=0.0.0.0
API_PORT=8003

# Ollama & Embeddings
EMB_MODEL=nomic-embed-text
OLLAMA_HOST=http://127.0.0.1:11434
EMBEDDING_TIMEOUT=30
EMBEDDING_RETRIES=3

# ChromaDB
CHROMA_PATH=../data/chroma_db
CHROMA_COLLECTION_NAME=rag_docs
CHROMA_DISTANCE=cosine               # cosine, l2, ip

# Text Processing
CHARS_PER_TOKEN=4.0
CHUNK_TOKENS=800                     # Target chunk size in tokens
CHUNK_OVERLAP_TOKENS=140             # Overlap between chunks

# Hashing & Deduplication
HASH_ALGO=xxh3                       # xxh3 or md5
INGEST_BATCH_SIZE=128
MAX_WORKERS=4

# File Paths
RAW_DATA_DIR=../data/raw
UPLOAD_DIR=../data/uploads           # Temporary upload directory

# Logging
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=ingestion.log
LOG_FORMAT=console                   # console or json
```

### Validation

All settings are validated on startup via Pydantic:

```python
# ✅ Valid
settings = Settings(APP_ENV="prod", CHROMA_DISTANCE="cosine")

# ❌ Invalid - raises ValidationError
settings = Settings(APP_ENV="invalid", CHROMA_DISTANCE="euclidean")
```

## 📊 Metrics System

The pipeline includes comprehensive metrics tracking for throughput, latency, and errors.

### Tracked Metrics

**Throughput**:
- Files per second
- Chunks per second  
- Bytes per second

**Latency** (P50, P95, P99 percentiles in milliseconds):
- Extraction
- Chunking
- Embedding
- Upsert

**Errors**:
- Per-operation error counts
- Total errors

**Timing**:
- Total pipeline duration
- Time breakdown by operation

### Usage Example

```python
from app.metrics import MetricsCollector
import time

collector = MetricsCollector()
start = time.time()

# Record extraction
try:
    # Extract text...
    collector.record_extraction(time.time() - start)
except Exception as e:
    collector.record_extraction(time.time() - start, error=True)

# Finalize metrics
metrics = collector.finalize(
    total_duration_seconds=time.time() - start,
    files_processed=10,
    total_chunks=100,
    total_bytes=50000,
)

print(metrics)
# Output: Throughput: 10.00 files/s, 100.00 chunks/s | Errors: 0 total | Time: 1.00s
```

### JSON Output

```python
import json
metrics_dict = metrics.to_dict()
print(json.dumps(metrics_dict, indent=2))
```

## 💾 Memory Optimization

The ingestion pipeline includes advanced memory optimization for processing large document collections efficiently.

### Stream Processing

Chunks are generated and processed incrementally rather than all at once:

```python
# ✅ Efficient - streaming async generator
async for chunk in stream_chunks(large_text):
    # Process chunk individually
    # Memory only holds current chunk + batch buffer

# ❌ Inefficient - loads all chunks at once
chunks = chunk_text(large_text)  # All in memory
for chunk in chunks:
    # Process...
```

### Adaptive Batch Sizing

Batch size automatically adjusts based on average chunk size and available memory:

```bash
# Configuration (in .env or environment)
ADAPTIVE_BATCH_SIZE=true          # Enable adaptive sizing
MEMORY_BUFFER_MB=100              # Target memory buffer (MB)
STREAM_CHUNK_SIZE=65536           # File read buffer (64KB default)
INGEST_BATCH_SIZE=128             # Base batch size
```

**How it works**:
1. Tracks average chunk size during processing
2. Calculates optimal batch size to stay within `MEMORY_BUFFER_MB`
3. Adjusts every 10 chunks to respond to content changes
4. Respects minimum (1) and maximum (4x base size) constraints

### Memory Monitoring

```python
from app.memory import MemoryMonitor, calculate_adaptive_batch_size

# Monitor memory during batch processing
monitor = MemoryMonitor(target_memory_mb=100)

for chunk in chunks:
    chunk_size = len(chunk.encode('utf-8'))
    monitor.record_chunk(chunk_size)
    
    if monitor.get_current_mb() > 95:
        # Flush before reaching limit
        await flush_buffer()

print(monitor)
# Output: Memory: 45.2MB (peak 92.1MB), Chunks: 1240, Avg size: 2105B
```

### Usage Optimization

**For large files**:
```bash
# Smaller chunk size reduces memory footprint
CHUNK_TOKENS=400                  # Default 800, halve for large docs
INGEST_BATCH_SIZE=64              # Reduce batch size
MEMORY_BUFFER_MB=50               # Stricter memory limit
```

**For many small files**:
```bash
# Larger batch size for throughput
INGEST_BATCH_SIZE=256             # Increased batching
MEMORY_BUFFER_MB=200              # More generous buffer
MAX_WORKERS=8                      # More concurrent processing
```

**Performance tuning tips**:
- Start with `ADAPTIVE_BATCH_SIZE=true` for automatic optimization
- Monitor logs for memory warnings
- Adjust `MEMORY_BUFFER_MB` based on available system memory
- Use `make test` to verify settings don't break functionality


Output:
```json
{
  "timing": {
    "total_duration_seconds": 1.0,
    "extraction_seconds": 0.5,
    "chunking_seconds": 0.2,
    "embedding_seconds": 0.2,
    "upsert_seconds": 0.1
  },
  "throughput": {
    "files_per_second": 10.0,
    "chunks_per_second": 100.0,
    "bytes_per_second": 50000.0
  },
  "errors": {
    "extraction": 0,
    "chunking": 0,
    "embedding": 0,
    "upsert": 0,
    "total": 0
  },
  "latency_percentiles_ms": {
    "extraction": {"p50": 50.0, "p95": 55.0, "p99": 59.0},
    "chunking": {"p50": 20.0, "p95": 22.0, "p99": 24.0},
    "embedding": {"p50": 20.0, "p95": 22.0, "p99": 24.0},
    "upsert": {"p50": 10.0, "p95": 11.0, "p99": 12.0}
  }
}
```

## 🧪 Testing

Comprehensive test suite with 88 tests covering all modules.

### Run Tests

```bash
# Quick test (quiet mode)
make test

# Verbose output
make test-v

# Coverage report
make test-cov

# Watch mode (auto-run on changes)
make test-watch

# Run tests in Docker
make docker-test
```

### Test Coverage

- **app/auth.py**: JWT token validation
- **app/main.py**: FastAPI endpoints with 14 tests:
  - Health check (no auth required)
  - File upload with JWT authentication
  - Task status checking
  - Error handling (expired/invalid tokens, missing files)
  - Full integration flows
- **app/utils.py**: 23 tests (extraction, chunking, hashing)
- **app/config.py**: 17 tests (validation, constraints)
- **app/pipeline.py**: 9 tests (stats, iterator)
- **app/chroma.py**: 9 tests (mocks, integration)
- **app/memory.py**: 10 tests (memory tracking, GC)
- **app/metrics.py**: 20 tests (collection, percentiles, aggregation)

All tests pass:
```
102 passed in ~2.0s (local) or ~2.0s (Docker)
```

## 🎯 CLI Usage

The CLI provides intuitive commands with rich formatting and comprehensive options.

### ingest - Run Pipeline

Process documents with full control:

```bash
# Standard ingestion
python cli.py ingest

# Rebuild collection from scratch
python cli.py ingest --rebuild

# Delete ChromaDB completely and rebuild
python cli.py ingest --purge

# Preview without storing (dry-run)
python cli.py ingest --dry-run

# Verbose output with detailed stats
python cli.py ingest --verbose

# Quiet mode (suppress non-error logs)
python cli.py ingest -q

# Save logs to file
python cli.py ingest --log-file ingestion.log

# Combine options
python cli.py ingest --rebuild --verbose --log-file ingest.log
```

**Options:**
- `--rebuild`: Delete collection before ingesting (idempotent mode)
- `--purge`: Delete entire ChromaDB directory before ingesting
- `--dry-run`: Process documents but don't store in ChromaDB
- `--verbose / -q`: Enable verbose output or quiet mode
- `--log-file`: Save logs to a file

### config - Show Configuration

Display all settings in a formatted table:

```bash
python cli.py config
```

Shows application settings, paths, embedding config, chunking parameters, and pipeline settings.

### health - Validate Setup

Check if all dependencies are accessible:

```bash
python cli.py health

# Detailed output with paths
python cli.py health --verbose
```

Validates:
- Raw data directories (PDFs, TXTs)
- ChromaDB paths
- Directory accessibility

## 🔧 Makefile Commands

```bash
make help              # Show all commands
make install           # Install dependencies via uv
make run               # Run ingestion pipeline
make dev               # Development mode
make test              # Run tests (quiet)
make test-v            # Tests with verbose output
make test-cov          # Tests with coverage report
make test-watch        # Watch mode (auto-run tests)
make lint              # Run ruff linter
make clean             # Remove cache and build artifacts
make ingest            # Run ingestion
make config            # Show configuration
make health            # Health check
make docker-build      # Build Docker image (runtime target)
make docker-up         # Start stack (ollama + app)
make docker-down       # Stop stack
make docker-logs       # View stack logs
make docker-shell      # Open shell in app container
make docker-test       # Run tests in app container
```

## 🐳 Docker

### Quick Start

```bash
# Build Docker image
make docker-build

# Start full stack (ollama + redis + api + celery_worker)
make docker-up

# View logs
make docker-logs

# Run tests in container
make docker-test

# Stop stack
make docker-down
```

### Docker Compose Stack

The included `docker-compose.yml` provides a complete local development environment:
- **ollama**: Vector embedding service (port 11434)
- **redis**: Message broker for Celery (port 6379)
- **api**: FastAPI server (port 8003)
- **celery_worker**: Async job processor (with --pool=solo for macOS compatibility)

All services are health-checked and interdependent (API/Celery wait for Redis and Ollama).

### Testing in Docker

#### Run Unit/Integration Tests

```bash
# Start stack in background
make docker-up

# Run full test suite in container
make docker-test

# Clean up
make docker-down
```

#### Test API Endpoints in Docker

```bash
# Start just API services (ollama + redis + api + worker)
make docker-up

# Test health endpoint (no auth required)
curl http://127.0.0.1:8003/health

# Get JWT token from User Microservice (example)
TOKEN="<token from user service>"

# Test file upload (returns 202 Accepted)
curl -X POST http://localhost:8003/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf"

# Expected response:
# {
#   "task_id": "abc123...",
#   "status": "processing",
#   "message": "Document queued for processing"
# }

# Check task status
curl http://localhost:8003/v1/ingest/status/abc123... \
  -H "Authorization: Bearer $TOKEN"

# View logs while testing
make docker-logs
```

#### Docker Shell Access

```bash
# Open shell in API container for debugging
make docker-shell

# Inside container, run tests manually
python -m pytest tests/ -v

# Or check configuration
python -c "from config import settings; print(settings)"
```

### Dockerfile Highlights

- **Multi-stage build**: builder stage for compilation, minimal runtime stage
- **Python 3.13-slim**: Lightweight base image with Python 3.13.11
- **uv package manager**: Fast, deterministic dependency installation
- **Dev group optional**: Includes pytest and test dependencies in dev/docker builds
- **Non-root user**: Runs as `appuser` (uid 1000) for security
- **No build tools in runtime**: Keeps image small and secure
- **Ollama integration**: Seamless embedding function with ollama service

## 📋 API Reference

### extract_text_from_pdf

```python
from app.utils import extract_text_from_pdf

text = await extract_text_from_pdf("document.pdf")
```

### extract_text_from_txt

```python
from app.utils import extract_text_from_txt

text = await extract_text_from_txt("document.txt")
```

### chunk_text

```python
from app.utils import chunk_text

chunks = chunk_text("Long text here...")
```

### hash_text

```python
from app.utils import hash_text

file_hash = hash_text("document content")
```

### ChromaDBClient

```python
from app.chroma import chroma_client

collection = chroma_client.get_collection()
```

## 🚨 Error Handling

The pipeline includes comprehensive error handling:

- **File not found**: Logged and skipped
- **Extraction errors**: Caught, logged, and tracked in metrics
- **Chunking errors**: Handled gracefully
- **Embedding errors**: Retried with backoff
- **Upsert errors**: Failed records tracked

All errors are aggregated in metrics for monitoring.

## 🔍 Logging

Structured logging with configurable formats:

```python
from app.logger import logger

logger.debug("Detailed message")
logger.info("Information")
logger.warning("Warning")
logger.error("Error")
```

### Log Output

Console:
```
[2024-01-07 12:00:00] INFO: Processing file.pdf
[2024-01-07 12:00:01] INFO: Created 50 chunks
```

JSON:
```json
{"timestamp": "2024-01-07T12:00:00Z", "level": "INFO", "message": "Processing..."}
```

## 📦 Dependencies

### Core
- `pydantic>=2.11.0`: Configuration management
- `pydantic-settings>=2.6.0`: Environment variable loading
- `chromadb>=1.0.0`: Vector database
- `aiofiles>=24.1.0`: Async file operations
- `pypdf>=5.2.0`: PDF text extraction
- `typer>=0.15.0`: CLI framework
- `xxhash>=3.0.0`: Fast hashing for deduplication

### Dev
- `pytest>=7.0.0`: Testing framework
- `pytest-asyncio>=0.25.0`: Async test support
- `pytest-cov>=6.0.0`: Coverage reports
- `pytest-watch>=4.2.0`: Watch mode

## 🛠️ Development

### Setup

```bash
# Create venv and install
make install

# Activate venv
source .venv/bin/activate

# Run tests
make test
```

### Code Quality

- Linting: `make lint` (ruff)
- Type checking: Configured for Pylance (pyright)
- Tests: `make test`

### Git Workflow

```bash
# Make changes
git add app/
git commit -m "feat: add new feature"

# Run tests before push
make test

# Push
git push
```

### CI/CD

GitHub Actions automatically runs tests on every push/PR to main:
- **Workflow**: `.github/workflows/ingestion-microservice-test.yml`
- **Services**: Redis + Ollama (with `nomic-embed-text` model)
- **Tests**: Full pytest suite with coverage
- **Trigger**: Changes to `ingestion-microservice/**` paths

View workflow runs on GitHub Actions tab after pushing to repository.

## 📝 Notes

- All functions use timezone-aware UTC timestamps (`datetime.now(timezone.utc)`)
- Async/await throughout for I/O-bound operations
- Configuration validated on startup via Pydantic
- Deduplication via stable content hashing
- Metrics tracked per operation with percentile calculations

## 🤝 Contributing

1. Write tests first (TDD)
2. Run `make test` - all tests must pass
3. Run `make lint` - no linting errors
4. Metrics tests included for new features
5. Update this README if adding new features

## 📄 License

MITLOG_LEVEL=INFO
```

---

## Installation
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage
Run the ingestion pipeline with:

```bash
# Standard ingest
python3 -m scripts.ingest

# Rebuild collection (drop & recreate)
python3 -m scripts.ingest --rebuild

# Purge database directory and start fresh
python3 -m scripts.ingest --purge

# Change batch size
python3 -m scripts.ingest --batch 256
```

---

## Output Example
```
ingest_done files=2 chunks=2 added=2 skipped=0 secs=5.94
```

This means:
- 2 files processed
- 2 chunks created
- 2 new chunks added
- 0 duplicates skipped
- Process completed in 5.94 seconds
