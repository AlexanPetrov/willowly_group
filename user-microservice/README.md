# User Microservice

> **Part of [Willowly Group](https://github.com/AlexanPetrov/willowly_group)** - A microservices-based application platform

A production-ready FastAPI microservice for user management with JWT authentication, built with modern Python async patterns and PostgreSQL.

## 🚀 Features

### Core Functionality
- **User Management** - Create, read, update, delete users
- **JWT Authentication** - Secure token-based authentication with bcrypt password hashing
- **Batch Operations** - Create/delete multiple users in a single request (up to 1000)
- **Search & Filtering** - Full-text search and domain-based filtering
- **Pagination** - Configurable page-based pagination for list endpoints
- **Rate Limiting** - Protection against abuse with configurable limits
- **Redis Caching** - Automatic caching of user reads with TTL and invalidation
- **Monitoring** - Prometheus metrics and Grafana dashboards
- **Security Headers** - Protection against XSS, clickjacking, MIME sniffing, and other attacks

### Technical Features
- **Async/Await** - Full async support with asyncpg and SQLAlchemy 2.0
- **Database Migrations** - Version-controlled schema changes with Alembic
- **Structured Logging** - JSON and console logging with request tracking
- **Input Validation** - Pydantic schemas with comprehensive validation
- **Error Handling** - Standardized error responses with detailed messages
- **Security Headers** - OWASP-recommended headers (CSP, HSTS, X-Frame-Options, etc.)
- **Testing** - 113 tests covering all layers (API, services, CRUD, utils, cache, metrics, security)
- **Environment-Based Config** - Separate dev/prod configurations
- **Docker Compose** - Multi-container setup with app, PostgreSQL, Redis, Prometheus, Grafana

## 📋 Requirements

### Option 1: Local Development
- Python 3.12+
- PostgreSQL 17+
- Redis 7.0+
- uv (Python package manager)

### Option 2: Docker (Recommended)
- Docker 20.10+
- Docker Compose 2.0+

**Docker includes:** App + PostgreSQL + Redis + Prometheus + Grafana - all configured and ready to use!

## 🛠️ Installation

Choose between local development or Docker. Docker is recommended for new developers or teams.

---

### 🐳 Quick Start with Docker (Recommended)

**No PostgreSQL or Python installation required!**

```bash
# Clone and start
git clone https://github.com/AlexanPetrov/willowly_group.git
cd willowly_group/user-microservice

# Build and start all services
make docker-build
make docker-up

# Run migrations
make docker-migrate

# Done! API at http://localhost:8000
```

**Verify it's working:**
```bash
curl http://localhost:8000/health
```

Skip to [Docker Commands](#-docker-commands) section below.

---

### 💻 Local Development Setup

### 1. Clone & Setup

```bash
git clone https://github.com/AlexanPetrov/willowly_group.git
cd willowly_group/user-microservice
uv venv
source .venv/bin/activate  # macOS/Linux
uv sync
```

### 2. Database Setup

```bash
# Start PostgreSQL
brew services start postgresql@17

# Create database and user
psql postgres
```

```sql
CREATE ROLE api_user WITH LOGIN PASSWORD 'pass123';
CREATE DATABASE user_microservice_db;
\c user_microservice_db
GRANT USAGE ON SCHEMA public TO api_user;
GRANT CREATE ON SCHEMA public TO api_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO api_user;
\q
```

### 3. Redis Setup

```bash
# Install Redis
brew install redis

# Start Redis service (runs in background)
brew services start redis

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

### 4. Environment Configuration

```bash
# Development uses .env.dev (already configured)
# For production, copy the template:
cp .env.prod.example .env.prod
nano .env.prod  # Edit with your production values
```

**Important:** Generate a new JWT secret for production:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Run Migrations

```bash
make migrate-up
# or
uv run alembic upgrade head
```

## 🚀 Running the Service

### Local Development (auto-reload)
```bash
make dev
# or
APP_ENV=dev uv run uvicorn app.main:app --reload
```

### Docker Development
```bash
make docker-up        # Start containers
make docker-logs-app  # View logs
```

### Production Mode (Local)
```bash
make prod
# or
APP_ENV=prod uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server runs at: `http://localhost:8000`

**Swagger UI:** `http://localhost:8000/docs`

## 📚 API Documentation

### Authentication Endpoints

#### Register New User
```http
POST /auth/register
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securepass123"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2025-12-10T10:30:00Z"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "securepass123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Get Current User Profile (Protected)
```http
GET /users/me
Authorization: Bearer <your_access_token>
```

### User Management Endpoints

#### List Users (Paginated)
```http
GET /users?page=1&limit=10&sort_by=name&sort_order=asc
```

**Query Parameters:**
- `page` (default: 1) - Page number
- `limit` (default: 10, max: 100) - Items per page
- `sort_by` (optional) - Sort field: `name`, `email`, `created_at`
- `sort_order` (optional) - Sort order: `asc`, `desc`
- `email_domain` (optional) - Filter by email domain (e.g., `gmail.com`)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "is_active": true,
      "created_at": "2025-12-10T10:30:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 10,
  "pages": 10
}
```

#### Search Users
```http
GET /users/search?q=john&page=1&limit=10
```

Searches in both name and email fields (case-insensitive).

#### Get User by ID
```http
GET /users/{user_id}
```

#### Delete User
```http
DELETE /users/{user_id}
```

Returns the deleted user data.

### Batch Operations

#### Batch Create Users
```http
POST /users/batch-create
Content-Type: application/json

{
  "items": [
    {
      "name": "Alice Smith",
      "email": "alice@example.com",
      "password": "password123"
    },
    {
      "name": "Bob Johnson",
      "email": "bob@example.com",
      "password": "password456"
    }
  ]
}
```

**Limits:** Max 1000 users per batch

**Response:**
```json
{
  "items": [ /* created users */ ],
  "created": 2
}
```

#### Batch Delete Users
```http
POST /users/batch-delete
Content-Type: application/json

{
  "ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "items": [ /* deleted users */ ],
  "deleted": 5
}
```

## 🔐 Using JWT Authentication in Swagger

1. **Register** a new user via `POST /auth/register`
2. **Login** via `POST /auth/login` - copy the `access_token`
3. **Authorize** - Click the 🔓 button (top right)
   - Paste your token (just the token, not "bearer")
   - Click "Authorize" then "Close"
4. **Use Protected Endpoints** - The 🔒 icon shows which endpoints require auth

**Token expiration:**
- Development: 30 minutes
- Production: 15 minutes

## � Security Features

### Security Headers

All API responses include OWASP-recommended security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking attacks |
| `X-XSS-Protection` | `1; mode=block` | Enables XSS filter in older browsers |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer information |
| `Content-Security-Policy` | `default-src 'self'; ...` | Prevents XSS and data injection |
| `Permissions-Policy` | `geolocation=(), ...` | Controls browser features |
| `Strict-Transport-Security` | `max-age=31536000` | Forces HTTPS (production only) |

**Verify headers:**
```bash
curl -I http://localhost:8000/health | grep -i "x-\|content-security\|referrer"
```

### Password Security

- **Bcrypt hashing** - Industry-standard password hashing with automatic salt
- **Minimum complexity** - Enforced in validation (can be customized)
- **Never logged** - Passwords excluded from all log output

### JWT Security

- **HS256 algorithm** - Secure token signing
- **Short expiration** - 15-30 minutes to limit exposure
- **Secret key rotation** - Generate new keys for each environment
- **Token validation** - Signature and expiration checked on every request

### Rate Limiting

Protection against brute force and DoS attacks:
- **Batch operations**: 10-100 requests/minute
- **Write operations**: 60-300 requests/minute
- **Read operations**: 100-500 requests/minute

### Best Practices Implemented

✅ Input validation with Pydantic schemas  
✅ SQL injection protection (SQLAlchemy ORM)  
✅ CORS configuration (environment-specific origins)  
✅ Environment variable isolation (.env files)  
✅ Secure random token generation  
✅ Database connection pooling with limits  
✅ Request ID tracking for audit trails  
✅ Structured logging (no sensitive data)  

## �🚀 Redis Caching

### How It Works

The service automatically caches user data in Redis for fast reads:

**First Request (Cache Miss)**:
```bash
GET /users/1  # ~200ms (database query)
```

**Subsequent Requests (Cache Hit)**:
```bash
GET /users/1  # ~2ms (Redis lookup - 100x faster!)
```

### Cache Behavior

- **Cached Operations**: `GET /users/{id}`, user registration
- **TTL**: 5 minutes (300 seconds) by default
- **Invalidation**: Automatic on user update/delete
- **Keys**: `user:id:{id}` and `user:email:{email}`

### Local Redis Setup

```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# If not running, start it
brew services start redis

# View cached keys
redis-cli KEYS "user:*"

# Get specific cached user
redis-cli GET "user:id:1"

# Clear all cache
redis-cli FLUSHDB
```

### Docker Redis

Redis runs automatically in Docker Compose - no manual setup needed!

### Configuration

Edit `.env.dev` or `.env.prod`:

```bash
REDIS_URL=redis://localhost:6379/0  # Redis connection
CACHE_TTL=300                        # 5 minutes
CACHE_ENABLED=true                   # Enable/disable caching
```

## 📊 Monitoring & Metrics

### Prometheus + Grafana Stack

The service exposes Prometheus metrics for monitoring and includes Grafana for visualization.

### Available Metrics

- **HTTP Requests**: Total count by endpoint, method, status code
- **Request Duration**: p50, p95, p99 latency percentiles
- **In-Progress Requests**: Current active requests
- **Python Runtime**: GC stats, memory usage, CPU time
- **Process Metrics**: Virtual memory, open file descriptors

### Quick Start

**View Raw Metrics**:
```bash
curl http://localhost:8000/metrics
# or
make metrics
```

**Open Prometheus UI**:
```bash
make prometheus  # Opens http://localhost:9090
```

**Open Grafana**:
```bash
make grafana  # Opens http://localhost:3000
# Login: admin / admin
```

### Prometheus Queries

Try these in the Prometheus UI (http://localhost:9090):

```promql
# Request rate (requests/second)
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Requests by endpoint
sum by (handler) (rate(http_requests_total[5m]))
```

### Grafana Setup

1. **Add Prometheus Data Source**:
   - Go to http://localhost:3000
   - Login: admin/admin
   - Configuration → Data Sources → Add Prometheus
   - URL: `http://prometheus:9090`
   - Save & Test

2. **Import Dashboard**:
   - Dashboards → Import
   - Use ID: `14518` (FastAPI Observability)
   - Or create custom dashboard

### Monitoring Commands

```bash
make metrics                 # View /metrics endpoint
make prometheus              # Open Prometheus UI
make grafana                 # Open Grafana UI
make docker-logs-prometheus  # View Prometheus logs
make docker-logs-grafana     # View Grafana logs
```

## 🧪 Testing

### Run All Tests
```bash
make test
# or
uv run pytest tests/ -v
```

### Run Specific Test Suites
```bash
make test-api          # API integration tests
make test-services     # Business logic tests
make test-crud         # Database layer tests
make test-utils        # Utility function tests
```

### Test Coverage
- **113 tests** across all layers
- **100% pass rate**
- Covers: API endpoints, business logic, database operations, utils, caching, metrics, security headers, authentication, CRUD, pagination, filtering, search, batch operations

## � CI/CD Pipeline

This microservice is part of the [willowly_group](https://github.com/AlexanPetrov/willowly_group) monorepo. The GitHub Actions workflow automatically runs tests when user-microservice files change.

### Workflow Configuration
- **Location**: `/.github/workflows/user-microservice-test.yml` (at monorepo root)
- **Triggers**: Only runs when `user-microservice/**` files change
- **Scope**: Tests run in the user-microservice context

### Workflow Steps
1. ✅ Checkout code
2. ✅ Set up Python 3.12 and uv
3. ✅ Start PostgreSQL and Redis services
4. ✅ Run database migrations
5. ✅ Execute all 113 tests
6. ✅ Report results

### Viewing Results
- Check the **Actions** tab at [github.com/AlexanPetrov/willowly_group](https://github.com/AlexanPetrov/willowly_group/actions)
- Each push/PR shows a green ✅ or red ❌ status
- Click on workflow runs for detailed logs

### GitHub Actions Usage
- **Free Tier**: 2,000 minutes/month
- **Typical Usage**: ~10-15 minutes per workflow run
- **Path Filtering**: Only runs for user-microservice changes (conserves minutes)
- No billing unless you explicitly opt-in (spending limit defaults to $0)

## �🗄️ Database Management

### Makefile Commands
```bash
make db-start          # Start PostgreSQL service
make db-stop           # Stop PostgreSQL service
make db-connect        # Connect via psql
make db-reset          # Drop and recreate database with migrations
make db-truncate       # Clear all user data (keep schema)
```

### Migrations
```bash
make migrate-generate  # Create new migration (autogenerate)
make migrate-up        # Apply all pending migrations
make migrate-down      # Rollback last migration
make migrate-current   # Show current version
make migrate-history   # Show migration history
```

## 🐳 Docker Commands

### Basic Operations
```bash
make docker-build     # Build Docker images
make docker-up        # Start all containers (app + PostgreSQL)
make docker-down      # Stop and remove containers
make docker-restart   # Restart containers
make docker-ps        # Show running containers status
```

### Logs and Monitoring
```bash
make docker-logs      # View logs from all containers
make docker-logs-app  # View app logs only
make docker-logs-db   # View database logs only
```

### Shell Access
```bash
make docker-shell     # Open bash shell in app container
make docker-shell-db  # Open psql shell in database
```

### Database Operations
```bash
make docker-migrate   # Run migrations in Docker
make docker-test      # Run tests in Docker container
```

### Cleanup
```bash
make docker-clean     # Remove containers, volumes, networks
```

### Docker Architecture

```
┌─────────────────────────────────────┐
│  Docker Compose Network             │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │  App (8000)  │──│  DB (5432)  │ │
│  │  FastAPI     │  │  PostgreSQL │ │
│  └──────────────┘  └─────────────┘ │
│         │                │          │
└─────────┼────────────────┼──────────┘
          │                │
     localhost:8000   localhost:5432
```

**Key Points:**
- App container uses service name `db` to connect to PostgreSQL
- PostgreSQL data persists in Docker volume `user_microservice_postgres_data`
- Hot reload enabled: changes to `app/` directory auto-reload the server
- Health checks ensure database is ready before starting app

## ⚙️ Configuration

### Environment Variables

**Development (`.env.dev`):**
```bash
APP_ENV=dev
DB_URL=postgresql+asyncpg://api_user:pass123@localhost:5432/user_microservice_db
JWT_SECRET_KEY=your-dev-secret-key
JWT_EXPIRATION_MINUTES=30
LOG_LEVEL=DEBUG
RATE_LIMIT_READ=500/minute
RATE_LIMIT_WRITE=300/minute
```

**Production (`.env.prod`):**
```bash
APP_ENV=production
DB_URL=postgresql+asyncpg://prod_user:STRONG_PASSWORD@prod-host/prod_db
JWT_SECRET_KEY=GENERATE_NEW_SECRET_FOR_PRODUCTION
JWT_EXPIRATION_MINUTES=15
LOG_LEVEL=INFO
RATE_LIMIT_READ=100/minute
RATE_LIMIT_WRITE=60/minute
```

### Key Settings

| Setting | Dev | Prod | Description |
|---------|-----|------|-------------|
| `JWT_EXPIRATION_MINUTES` | 30 | 15 | Token lifetime |
| `LOG_LEVEL` | DEBUG | INFO | Logging verbosity |
| `LOG_FORMAT` | console | json | Log format |
| `RATE_LIMIT_READ` | 500/min | 100/min | GET request limits |
| `RATE_LIMIT_WRITE` | 300/min | 60/min | POST/DELETE limits |
| `MAX_BATCH_SIZE` | 1000 | 1000 | Max items in batch ops |

## 📁 Project Structure

```
User_Microservice/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app & startup
│   ├── config.py         # Settings & environment config
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic schemas
│   ├── routes.py         # API endpoints
│   ├── services.py       # Business logic
│   ├── crud.py           # Database operations
│   ├── auth.py           # JWT & password handling
│   ├── dependencies.py   # FastAPI dependencies
│   ├── db.py             # Database session management
│   ├── logger.py         # Structured logging
│   └── utils.py          # Utility functions
├── tests/
│   ├── conftest.py       # Test fixtures
│   ├── test_api.py       # API integration tests
│   ├── test_services.py  # Service layer tests
│   ├── test_crud.py      # Database tests
│   └── test_utils.py     # Utility tests
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py           # Alembic config
├── .env.dev              # Development config
├── .env.prod.example     # Production template
├── Makefile              # Common commands
├── pyproject.toml        # Project dependencies
└── alembic.ini           # Alembic configuration
```

## 🔧 Development Workflow

### Recommended Daily Workflow

**For most development:**
```bash
make dev              # Run locally (fastest iteration)
make test             # Test locally (fastest feedback)
```

**Before committing/deploying:**
```bash
make docker-build     # Build Docker image
make docker-up        # Verify in Docker environment
make docker-test      # Run tests in Docker (production parity)
make docker-down      # Stop containers
```

**Why this approach?**
- Local development is faster (hot reload, easier debugging)
- Docker validation catches environment-specific issues
- Best of both worlds: speed + reliability

### Making Database Changes

1. **Modify models** in `app/models.py`
2. **Generate migration:**
   ```bash
   make migrate-generate         # Local
   make docker-migrate-generate  # Docker
   # Enter migration message when prompted
   ```
3. **Review migration** in `alembic/versions/`
4. **Apply migration:**
   ```bash
   make migrate-up        # Local
   make docker-migrate    # Docker
   ```

### Adding New Endpoints

1. **Define schema** in `app/schemas.py` (request/response models)
2. **Add CRUD function** in `app/crud.py` (database operations)
3. **Add service function** in `app/services.py` (business logic)
4. **Add route** in `app/routes.py` (HTTP endpoint)
5. **Write tests** in `tests/test_*.py`

### Code Quality

```bash
make lint              # Run ruff linter
make clean             # Remove cache files
```

## 🚢 Deployment

### Docker Deployment (Recommended)

**Local Docker Testing:**
```bash
# Build and test Docker setup locally
make docker-build
make docker-up
make docker-migrate
make docker-test

# Test API
curl http://localhost:8000/health
```

**Production Docker Deployment:**

1. **Update `.env.prod`:**
   ```bash
   # Generate new JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Update .env.prod with:
   # - Production database URL
   # - New JWT secret
   # - Production CORS origins
   ```

2. **Deploy with Docker Compose:**
   ```bash
   APP_ENV=prod docker-compose up -d
   docker-compose exec app alembic upgrade head
   ```

**Cloud Deployment Options:**
- **AWS ECS/Fargate** - Use Dockerfile, connect to RDS PostgreSQL
- **Google Cloud Run** - Use Dockerfile, connect to Cloud SQL
- **Azure Container Instances** - Use Dockerfile, connect to Azure Database
- **DigitalOcean App Platform** - Use Dockerfile, connect to Managed PostgreSQL
- **Fly.io** - Use Dockerfile with PostgreSQL add-on

### Production Checklist

**Security:**
- [ ] Generate new `JWT_SECRET_KEY` for production (32+ chars)
- [ ] Update `DB_URL` with production database connection string
- [ ] Set `CORS_ORIGINS` to your frontend domain(s)
- [ ] Set up SSL/TLS certificates (handled by cloud provider or reverse proxy)
- [ ] Review and adjust rate limits based on expected traffic

**Infrastructure:**
- [ ] Configure Redis for production (consider Redis Sentinel or Cluster)
- [ ] Set up database backups (daily minimum)
- [ ] Configure log aggregation (ELK stack, CloudWatch, etc.)
- [ ] Set up Prometheus + Grafana for monitoring
- [ ] Configure alerts for error rates, latency, downtime

**Configuration:**
- [ ] Change `LOG_LEVEL` to `INFO` (or `WARNING` for less verbosity)
- [ ] Set `CACHE_TTL` based on your data freshness requirements
- [ ] Adjust database connection pool settings
- [ ] Test Docker image locally before deploying
- [ ] Configure environment variables in deployment platform

**DevOps:**
- [ ] Set up CI/CD pipeline (GitHub Actions, GitLab CI, etc.)
- [ ] Configure auto-scaling based on metrics
- [ ] Set up health check monitoring
- [ ] Document runbooks for common issues

## 📊 Rate Limiting

Protects against abuse with configurable per-minute limits:

- **Batch Operations:** 10/minute (prod), 100/minute (dev)
- **Write Operations:** 60/minute (prod), 300/minute (dev)
- **Read Operations:** 100/minute (prod), 500/minute (dev)

Rate limits are disabled during testing.

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql

# Verify database exists
psql -U api_user -d user_microservice_db -c "SELECT 1"
```

### Migration Issues
```bash
# Check current version
make migrate-current

# View migration history
make migrate-history

# Reset database (WARNING: deletes all data)
make db-reset
```

### Environment Loading Issues
```bash
# Verify which config is loaded
APP_ENV=dev uv run python -c "from app.config import settings; print(settings.APP_ENV, settings.LOG_LEVEL)"
```

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Add/update tests
4. Run `make test` to ensure all tests pass
5. Run `make lint` to check code style
6. Submit a pull request

## 📝 License

[Your License Here]

## 🔗 Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Made with ❤️ using FastAPI, PostgreSQL, and modern Python**
