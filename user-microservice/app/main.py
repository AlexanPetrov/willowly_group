from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from .config import settings
from .routes import router
from .db import dispose_engine
from .cache import cache_manager
from .logger import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# App lifecycle hook
@asynccontextmanager
async def lifespan(app: FastAPI): 
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    logger.info("Database schema managed by Alembic migrations")
    
    # Connect to Redis cache
    if settings.CACHE_ENABLED:
        await cache_manager.connect()
    
    yield
    
    # Cleanup on shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    if settings.CACHE_ENABLED:
        await cache_manager.disconnect()
    await dispose_engine()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Request ID tracking middleware (must be first)
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracing across logs."""
    # Try to get request ID from header, or generate new one
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Store in request state for access in routes/services
    request.state.request_id = request_id
    
    # Execute request
    response = await call_next(request)
    
    # Add request ID to response headers for client tracking
    response.headers["X-Request-ID"] = request_id
    
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and their response times."""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log request with request ID
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} - Request received"
    )
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log response with request ID
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration:.3f}s"
        )
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Error: {str(e)} - "
            f"Duration: {duration:.3f}s",
            exc_info=True
        )
        raise


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses for protection against common attacks."""
    response = await call_next(request)
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking attacks
    response.headers["X-Frame-Options"] = "DENY"
    
    # Enable XSS protection in older browsers
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Enforce HTTPS in production (only if not in dev/test)
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Referrer policy - only send origin for same-origin requests
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Content Security Policy - prevent XSS and data injection
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    
    # Permissions policy - control browser features
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response

 
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach limiter to app state and register exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)

# Prometheus metrics instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

# Initialize and expose metrics
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=False,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

# Instrument the app and expose /metrics endpoint
instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)
