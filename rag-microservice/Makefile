.PHONY: help install run dev prod test lint clean docker-build docker-up docker-down docker-restart docker-logs docker-shell docker-ps docker-test docker-clean build metrics

help:
	@echo "Available commands:"
	@echo ""
	@echo "Local Development:"
	@echo "  make install          - Install dependencies using uv"
	@echo "  make run              - Run the FastAPI server (port 8001)"
	@echo "  make dev              - Run server in development mode with auto-reload"
	@echo "  make prod             - Run server in production mode"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run ruff linter"
	@echo "  make clean            - Remove cache files and build artifacts"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make build            - Alias for docker-build"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-up        - Start services with docker-compose (dev)"
	@echo "  make docker-down      - Stop and remove containers"
	@echo "  make docker-restart   - Restart services"
	@echo "  make docker-logs      - View logs from all containers"
	@echo "  make docker-shell     - Open bash shell in app container"
	@echo "  make docker-ps        - Show running containers"
	@echo "  make docker-test      - Run tests in container"
	@echo "  make docker-clean     - Remove containers and volumes"
	@echo ""
	@echo "Docker Production:"
	@echo "  make docker-prod      - Start services in production mode"
	@echo ""
	@echo "Monitoring:"
	@echo "  make metrics          - Open Prometheus metrics endpoint"
	@echo ""
	@echo "Features:"
	@echo "  - JWT Authentication with user-microservice"
	@echo "  - Streaming responses with chunked LLM output"
	@echo "  - Document metadata and retrieval statistics in responses"
	@echo "  - Exponential backoff retry logic for Ollama resilience"
	@echo "  - Strict input validation (k: 1-20, similarity: 0-1, tokens: 1-2048)"

install:
	uv sync

run:
	APP_ENV=dev uv run python -m uvicorn app.main:app --port 8001

dev:
	APP_ENV=dev uv run python -m uvicorn app.main:app --reload --reload-dir app --reload-dir core --port 8001

prod:
	APP_ENV=prod uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

test:
	uv run python -m pytest tests/ -q

lint:
	uv run ruff check app/ core/

clean:
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf core/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# ============================================================================
# Docker Commands
# ============================================================================

build: docker-build

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 3
	@echo "RAG service started! API: http://localhost:8001 | Docs: http://localhost:8001/docs"

docker-down:
	docker-compose down

docker-restart:
	docker-compose restart

docker-logs:
	docker-compose logs -f

docker-shell:
	docker-compose exec app /bin/bash

docker-ps:
	docker-compose ps

# Note: docker-test assumes the image was built with dev dependencies (pytest)
docker-test:
	docker-compose exec app python -m pytest tests/ -v

docker-clean:
	docker-compose down -v
	docker system prune -f
	@echo "Docker cleanup complete!"

docker-prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
	@echo "Production RAG service started!"

# ============================================================================
# Monitoring Commands
# ============================================================================

metrics:
	@echo "Opening metrics endpoint..."
	@open http://localhost:8001/metrics || xdg-open http://localhost:8001/metrics 2>/dev/null || echo "Metrics available at: http://localhost:8001/metrics"
