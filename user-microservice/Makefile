.PHONY: help install run dev prod test test-v test-crud test-services test-api test-utils lint clean db-start db-stop db-connect db-reset db-truncate migrate-generate migrate-up migrate-down migrate-current migrate-history docker-build docker-up docker-down docker-restart docker-logs docker-logs-app docker-logs-db docker-shell docker-shell-db docker-ps docker-migrate docker-test docker-clean docker-clean-images docker-prod

help:
	@echo "Available commands:"
	@echo ""
	@echo "Local Development:"
	@echo "  make install          - Install dependencies using uv"
	@echo "  make run              - Run the FastAPI server (dev environment)"
	@echo "  make dev              - Run server in development mode with auto-reload"
	@echo "  make prod             - Run server in production mode"
	@echo "  make test             - Run all tests"
	@echo "  make test-v           - Run all tests with verbose output"
	@echo "  make test-crud        - Run database layer tests only"
	@echo "  make test-services    - Run business logic tests only"
	@echo "  make test-api         - Run API integration tests only"
	@echo "  make test-utils       - Run utility tests only"
	@echo "  make lint             - Run ruff linter"
	@echo "  make clean            - Remove cache files and build artifacts"
	@echo ""
	@echo "Local Database:"
	@echo "  make db-start         - Start PostgreSQL service"
	@echo "  make db-stop          - Stop PostgreSQL service"
	@echo "  make db-connect       - Connect to database via psql"
	@echo "  make db-reset         - Drop and recreate database with migrations"
	@echo "  make db-truncate      - Clear all data from users table"
	@echo ""
	@echo "Migrations:"
	@echo "  make migrate-generate - Generate new Alembic migration (autogenerate)"
	@echo "  make migrate-up       - Apply all pending migrations"
	@echo "  make migrate-down     - Rollback last migration"
	@echo "  make migrate-current  - Show current migration version"
	@echo "  make migrate-history  - Show migration history"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make docker-build     - Build Docker images"
	@echo "  make docker-up        - Start all containers (app + db)"
	@echo "  make docker-down      - Stop and remove all containers"
	@echo "  make docker-restart   - Restart all containers"
	@echo "  make docker-logs      - View logs from all containers"
	@echo "  make docker-logs-app  - View logs from app container only"
	@echo "  make docker-logs-db   - View logs from database container only"
	@echo "  make docker-shell     - Open bash shell in app container"
	@echo "  make docker-shell-db  - Open psql shell in database container"
	@echo "  make docker-ps        - Show running containers"
	@echo "  make docker-migrate   - Run migrations in Docker container"
	@echo "  make docker-test      - Run tests in Docker container"
	@echo "  make docker-clean     - Remove containers, volumes, and networks"
	@echo "  make docker-clean-images - Delete unused Docker images (tmp-test, dangling)"
	@echo ""
	@echo "Monitoring:"
	@echo "  make metrics          - Open Prometheus metrics endpoint"
	@echo "  make prometheus       - Open Prometheus UI"
	@echo "  make grafana          - Open Grafana UI (admin/admin)"
	@echo "  make docker-logs-prometheus - View Prometheus logs"
	@echo "  make docker-logs-grafana - View Grafana logs"
install:
	uv sync

run:
	APP_ENV=dev uv run python -m uvicorn app.main:app

dev:
	APP_ENV=dev uv run python -m uvicorn app.main:app --reload --reload-dir app --reload-dir alembic

prod:
	APP_ENV=prod uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	uv run python -m pytest tests/ -q

test-v:
	uv run python -m pytest tests/ -v

test-crud:
	uv run python -m pytest tests/test_crud.py -v

test-services:
	uv run python -m pytest tests/test_services.py -v

test-api:
	uv run python -m pytest tests/test_api.py -v

test-utils:
	uv run python -m pytest tests/test_utils.py -v

lint:
	uv run ruff check app/

clean:
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

db-start:
	brew services start postgresql@17

db-stop:
	brew services stop postgresql@17

db-connect:
	psql -U api_user -d user_microservice_db

db-reset:
	@echo "Dropping and recreating database..."
	psql -U api_user -d postgres -c "DROP DATABASE IF EXISTS user_microservice_db;"
	psql -U api_user -d postgres -c "CREATE DATABASE user_microservice_db;"
	@echo "Running migrations..."
	uv run alembic upgrade head
	@echo "Database reset complete!"

db-truncate:
	@echo "Clearing all users from database..."
	psql -U api_user -d user_microservice_db -c "TRUNCATE TABLE users RESTART IDENTITY CASCADE;"
	@echo "Users table cleared!"

migrate-generate:
	@read -p "Enter migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

migrate-up:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

migrate-current:
	uv run alembic current

migrate-history:
	uv run alembic history --verbose

# ============================================================================
# Docker Commands
# ============================================================================

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@echo "Services started! App: http://localhost:8000 | Docs: http://localhost:8000/docs"

docker-down:
	docker-compose down

docker-restart:
	docker-compose restart

docker-logs:
	docker-compose logs -f

docker-logs-app:
	docker-compose logs -f app

docker-logs-db:
	docker-compose logs -f db

docker-shell:
	docker-compose exec app /bin/bash

docker-shell-db:
	docker-compose exec db psql -U api_user -d user_microservice_db

docker-ps:
	docker-compose ps

docker-migrate:
	docker-compose exec app alembic upgrade head

docker-test:
	docker-compose exec app python -m pytest tests/ -v

docker-clean:
	docker-compose down -v
	docker system prune -f
	@echo "Docker cleanup complete!"

docker-clean-images:
	docker image rm tmp-test 2>/dev/null || true
	docker image prune -f
	@echo "Unused images removed!"

docker-prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# ============================================================================
# Monitoring Commands
# ============================================================================

metrics:
	@echo "Opening metrics endpoint..."
	@open http://localhost:8000/metrics || xdg-open http://localhost:8000/metrics 2>/dev/null || echo "Metrics available at: http://localhost:8000/metrics"

prometheus:
	@echo "Opening Prometheus UI..."
	@open http://localhost:9090 || xdg-open http://localhost:9090 2>/dev/null || echo "Prometheus available at: http://localhost:9090"

grafana:
	@echo "Opening Grafana UI (username: admin, password: admin)..."
	@open http://localhost:3000 || xdg-open http://localhost:3000 2>/dev/null || echo "Grafana available at: http://localhost:3000"

docker-logs-prometheus:
	docker-compose logs -f prometheus

docker-logs-grafana:
	docker-compose logs -f grafana
