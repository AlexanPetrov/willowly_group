# RAG Microservice

Retrieval-Augmented Generation (RAG) microservice. Takes a user query, retrieves the most relevant document chunks from **ChromaDB**, and generates an answer using **Ollama** LLM.

## Features

- **JWT Authentication**: Validates access tokens from the user-microservice
- **Semantic Search**: Retrieves relevant documents via vector embeddings (ChromaDB)
- **LLM Integration**: Generates answers using Ollama models with exponential backoff retry logic
- **Streaming Support**: Chunked responses for long-running queries (set `stream: true`)
- **Document Metadata**: Retrieval results include document source, path, and additional metadata
- **Retrieval Statistics**: Response includes stats (retrieved count, filtered count, top similarity score)
- **Input Validation**: Strict bounds on k (1–20), similarity (0.0–1.0), max_tokens (1–2048)
- **Health Checks**: Readiness and liveness endpoints with dependency status
- **Prometheus Metrics**: Request latency, retrieval stats, error rates via `/metrics`
- **Structured Logging**: Request ID correlation, service tracing, and retrieval metrics
- **Security Headers**: CORS, CSP, and security best practices built-in

## Prerequisites

- Python 3.13+
- Running `ollama serve` with a model available (e.g., `llama3.1:8b`)
- ChromaDB populated by `ingestion-microservice`
- Access to user-microservice for JWT secret key

## Quick Start

### With Docker (Recommended)

**Development** (with hot-reload):
```bash
make docker-up
# Visit http://localhost:8000/docs
```

**Production**:
```bash
make docker-prod
```

**Other docker commands**:
```bash
make docker-build      # Build image
make docker-down       # Stop services
make docker-logs       # View logs
make docker-test       # Run tests in container
make docker-shell      # Open container shell
make docker-clean      # Remove all containers/volumes
```

### Local Setup

#### Install Dependencies (with uv)

```bash
uv sync
```

#### Running

```bash
# Development with auto-reload
make dev

# Run tests
make test

# Lint code
make lint
```

## Configuration

### Environment Files

The service uses environment-specific configuration:

- **`.env.dev`** - Development (local/Docker dev) - committed
- **`.env.test`** - Testing (pytest) - committed
- **`.env.prod`** - Production (Docker prod) - committed template
- **`.env.*.example`** - Reference copies - committed

All files are committed with safe defaults. For production, edit `.env.prod` with real secrets before deployment.

### Environment Variables

**Development** (`.env.dev`):

```env
# Application
APP_ENV=dev
LOG_LEVEL=DEBUG
SECRET_KEY=your-secret-key-from-user-microservice
JWT_SECRET_KEY=your-jwt-secret-from-user-microservice

# Models
GEN_MODEL=llama3.1:8b
NUM_CTX=4096
NUM_PREDICT=512
TEMPERATURE=0.25

# ChromaDB
CHROMA_PATH=./data/chroma_db
CHROMA_COLLECTION_NAME=rag_docs
CHROMA_DISTANCE=cosine

# Retrieval
RETRIEVAL_K=2
MIN_SIMILARITY=0.65

# Ollama
OLLAMA_HOST=http://127.0.0.1:11434

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

**Production** (`.env.prod` - set real values):

```env
APP_ENV=prod
LOG_LEVEL=INFO
SECRET_KEY=<set-from-user-microservice>
JWT_SECRET_KEY=<set-from-user-microservice>
OLLAMA_HOST=http://ollama:11434  # or remote Ollama endpoint
ALLOWED_ORIGINS=https://yourdomain.com  # strict CORS
```

## Endpoints

### Health & Metadata

- **GET** `/` - Service metadata
- **GET** `/api/v1/health` - Health check with config and stats
- **GET** `/metrics` - Prometheus metrics

### RAG API (Authenticated)

- **POST** `/api/v1/query` - Execute RAG query
  - Requires: Bearer token in `Authorization` header
  - Request body:
    ```json
    {
      "text": "What are lions?",
      "k": 2,
      "min_similarity": 0.65,
      "max_tokens": 512,
      "stream": false
    }
  - Response:
    ```json
    {
      "response": "Lions are apex predators native to Africa's savannas...",
      "context_docs": ["Lions are apex predators..."],
      "similarities": [0.85],
      "metadata": [
        {
          "file": "animals.txt",
          "source_path": "data/raw/pdfs/animals.pdf",
          "extra": {
            "chunk_index": 0,
            "type": "pdf",
            "digest": "abf5dc92037c4573e53423e043d0ff10"
          }
        }
      ],
      "retrieval_stats": {
        "retrieved_count": 5,
        "filtered_count": 1,
        "top_similarity": 0.85
      }
    }
    ```
  - **Query Parameters**:
    - `text` (string, required) - User question
    - `k` (int, default=2, range 1-20) - Number of documents to retrieve
    - `min_similarity` (float, default=0.65, range 0.0-1.0) - Similarity threshold
    - `max_tokens` (int, default=512, range 1-2048) - Max generation tokens
    - `stream` (bool, default=false) - Stream response chunks

## Integration with User Microservice

### JWT Token Validation

- **Token Source**: Access tokens issued by user-microservice
- **Validation**: RAG validates JWT tokens using shared `SECRET_KEY` and `JWT_SECRET_KEY`
- **Claims Checked**: 
  - `sub` (subject/user ID) - required
  - `exp` (expiration) - enforced
  - Token type validation
- **Error Handling**: Invalid/expired tokens return 401 Unauthorized
- **Retry Logic**: Ollama calls use exponential backoff (up to 3 attempts, 0.5s → 1s → 2s delays)

### CORS Configuration

- **Allowed Origins**: Set in `ALLOWED_ORIGINS` env var (comma-separated)
- **Development**: Permissive (localhost:3000, 127.0.0.1:3000)
- **Production**: Strict (specific frontend domain only)

## Architecture

```
rag-microservice/
├── app/
│   ├── main.py           - FastAPI app, lifespan, middleware
│   ├── config.py         - Pydantic settings (environment-aware)
│   ├── auth.py           - JWT token validation
│   ├── logger.py         - Structured logging with correlation IDs
│   ├── middleware.py     - Request handling, security headers, graceful shutdown
│   ├── monitoring.py     - Prometheus metrics instrumentation
│   ├── routes.py         - API endpoints (/query, /health, /metrics)
│   ├── schemas.py        - Pydantic models (request/response validation)
│   └── dependencies.py   - Dependency injection
│
├── core/
│   ├── retriever.py      - ChromaDB vector search with similarity filtering
│   └── generator.py      - Ollama LLM response generation
│
├── tests/
│   ├── conftest.py       - Pytest fixtures and configuration
│   ├── test_auth.py      - Token validation tests (6 tests)
│   ├── test_retriever.py - Vector search tests (9 tests)
│   ├── test_generator.py - LLM generation tests (10 tests)
│   └── test_routes.py    - API endpoint tests (14 tests)
│
├── docker-compose.yml    - Development orchestration (hot-reload, mounts)
├── docker-compose.prod.yml - Production overrides (workers, logging, secrets)
├── Dockerfile            - Container image definition (Python 3.13-slim, uv)
├── .dockerignore         - Build context optimization
├── Makefile              - Development commands and docker-compose shortcuts
├── pyproject.toml        - Dependencies, project metadata, tool config
├── .env.dev              - Development configuration
├── .env.test             - Test configuration
├── .env.prod             - Production configuration template
└── README.md             - This file
```

## Development

### Local Setup

**1. Install uv** (fast Python package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Install dependencies**:
```bash
uv sync
```

**3. Activate virtual environment**:
```bash
source .venv/bin/activate
```

**4. Run development server**:
```bash
make dev
```

Server starts at `http://localhost:8000` with auto-reload on file changes.

### Running Tests

```bash
# Local tests
pytest tests/ -v

# Or via make
make test

# In Docker
make docker-test
```

All 39 tests pass (auth, retrieval, generation, routes).

### Code Quality

```bash
make lint          # Check with ruff
ruff format app/   # Auto-format code
```

## Deployment

### Docker Development (Recommended)

Development setup with hot-reload, volume mounts, and local debugging:

```bash
make docker-build    # Build image
make docker-up       # Start with hot-reload
```

**What this does:**
- Mounts source code directories (app/, core/, tests/) for live reloading
- Mounts ChromaDB volume for data persistence
- Connects to Ollama on `host.docker.internal:11434` (your macOS machine)
- Accessible at `http://localhost:8000`

**View logs**:
```bash
make docker-logs
```

**Run tests in container**:
```bash
make docker-test
```

**Stop services**:
```bash
make docker-down
```

### Docker Production

Production-optimized setup with multiple workers, strict logging, and secret injection:

```bash
# Set environment variables (or use .env.prod with real secrets)
export SECRET_KEY=<value-from-user-microservice>
export JWT_SECRET_KEY=<value-from-user-microservice>
export OLLAMA_HOST=<remote-ollama-endpoint>

make docker-prod
```

**What this does:**
- Runs 4 Uvicorn workers for concurrency
- INFO-level logging (production verbosity)
- No code mounts (immutable container)
- Strict CORS from `.env.prod`
- Automatic restart on failure
- Compatible with container orchestration (Kubernetes, etc.)

**Compose files**:
- `docker-compose.yml` - Base development config
- `docker-compose.prod.yml` - Production overrides (extends base)

Why two files here (vs one in user-microservice)?
- `docker-compose.yml` is optimized for local dev: hot-reload, code mounts, permissive CORS, optional local Ollama.
- `docker-compose.prod.yml` is a thin override: more workers, stricter logging/CORS, no code mounts, env-injected secrets. The user-microservice keeps prod and dev in one file because its stack (app + DB + Redis) shares the same compose profile, while RAG benefits from a lightweight prod override to drop mounts and crank worker count.

### Other Docker Commands

```bash
make docker-shell      # Open bash in running container
make docker-ps         # Show running containers
make docker-restart    # Restart services
make docker-clean      # Remove containers, volumes, prune images
```

## Troubleshooting

### "Collection not found" Error
- Ensure `ingestion-microservice` has populated ChromaDB at `CHROMA_PATH`
- Check collection name matches `CHROMA_COLLECTION_NAME`

### "Invalid token" Error
- Verify `SECRET_KEY` matches the one used by user-microservice
- Check token is not expired (`exp` claim)

### "Ollama connection refused"
- Ensure `ollama serve` is running
- Check `OLLAMA_HOST` is correct
- Verify the model is available: `ollama list`

## Monitoring

- **Metrics**: Available at `/metrics` (Prometheus format)
- **Logs**: Check stdout/stderr with `LOG_LEVEL` env var
- **Health**: `/api/v1/health` returns detailed dependency status

## License

Proprietary - Willowly Group
