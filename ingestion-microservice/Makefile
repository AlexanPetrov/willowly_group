.PHONY: help install run dev prod test lint clean docker-build docker-up docker-down docker-logs docker-shell api-up api-down api-logs worker-logs

help:
	@echo "Available commands:"
	@echo ""
	@echo "Local Development:"
	@echo "  make install          - Install dependencies using uv"
	@echo "  make run              - Run ingestion pipeline"
	@echo "  make dev              - Run in development mode with auto-reload"
	@echo "  make dev-worker       - Start Celery worker (macOS: uses --pool=solo)"
	@echo "  make dev-api          - Start FastAPI server"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run ruff linter"
	@echo "  make clean            - Remove cache files and build artifacts"
	@echo ""
	@echo "Pipeline Commands:"
	@echo "  make ingest           - Run ingestion pipeline"
	@echo "  make ingest-rebuild   - Rebuild collection (delete + re-ingest)"
	@echo "  make ingest-purge     - Purge all (delete entire ChromaDB + ingest)"
	@echo "  make ingest-dry-run   - Process documents but don't store"
	@echo "  make config           - Show current configuration"
	@echo "  make health           - Check dependencies"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-up        - Start full stack (ollama + redis + api + worker)"
	@echo "  make docker-down      - Stop full stack"
	@echo "  make api-up           - Start API only (for testing)"
	@echo "  make api-down         - Stop API"
	@echo "  make docker-logs      - View stack logs"
	@echo "  make api-logs         - View API logs only"
	@echo "  make worker-logs      - View Celery worker logs"
	@echo "  make docker-shell     - Open shell in API container"
	@echo "  make docker-test      - Run tests in container"
install:
	uv sync

run:
	uv run python cli.py ingest

dev:
	APP_ENV=dev uv run python cli.py ingest

test:
	uv run python -m pytest tests/ -q

test-v:
	uv run python -m pytest tests/ -v

test-cov:
	uv run python -m pytest tests/ --cov=app --cov-report=term-missing -v

test-watch:
	uv run pytest-watch tests/

lint:
	uv run --group dev ruff check app/ cli.py config.py tests/

clean:
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf tests/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Pipeline Commands

ingest:
	uv run python cli.py ingest

ingest-rebuild:
	uv run python cli.py ingest --rebuild

ingest-purge:
	uv run python cli.py ingest --purge

ingest-dry-run:
	uv run python cli.py ingest --dry-run

config:
	uv run python cli.py config

health:
	uv run python cli.py health

# Docker Commands

docker-build:
	docker build --target runtime -t ingestion-microservice:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

api-up:
	docker compose up -d ollama redis api

api-down:
	docker compose down

api-logs:
	docker compose logs -f api

worker-logs:
	docker compose logs -f celery_worker

dev-worker:
	uv run celery -A app.tasks.celery_app worker --pool=solo --loglevel=info

dev-api:
	uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload

docker-shell:
	docker compose exec api /bin/sh

docker-test:
	docker compose exec api python -m pytest tests/ -v
