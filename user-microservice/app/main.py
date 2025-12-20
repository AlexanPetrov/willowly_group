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
import asyncio
from typing import Optional

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


class GracefulShutdownManager:
    """Manages graceful shutdown of the application.
    
    Tracks active requests and ensures all in-flight requests complete
    before shutting down database and cache connections.
    """
    
    def __init__(self):
        self.is_shutting_down = False
        self.active_requests = 0
        self.shutdown_timeout = settings.GRACEFUL_SHUTDOWN_TIMEOUT
    
    def request_started(self):
        """Track a new incoming request."""
        if not self.is_shutting_down:
            self.active_requests += 1
    
    def request_finished(self):
        """Mark a request as completed."""
        self.active_requests -= 1
    
    async def initiate_shutdown(self):
        """Initiate graceful shutdown sequence."""
        if self.is_shutting_down:
            return
        
        logger.info("Graceful shutdown initiated")
        self.is_shutting_down = True
        
        # Wait for active requests to complete (with timeout)
        if self.active_requests > 0:
            logger.info(f"Waiting for {self.active_requests} active request(s) to complete...")
            
            start_time = asyncio.get_event_loop().time()
            while self.active_requests > 0:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= self.shutdown_timeout:
                    logger.warning(
                        f"Shutdown timeout ({self.shutdown_timeout}s) reached with "
                        f"{self.active_requests} request(s) still active - forcing shutdown"
                    )
                    break
                await asyncio.sleep(0.1)  # Check every 100ms
            
            if self.active_requests == 0:
                logger.info("All active requests completed successfully")
        else:
            logger.info("No active requests - proceeding with immediate shutdown")


# Global shutdown manager
shutdown_manager = GracefulShutdownManager()


# App lifecycle hook
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - handles startup and graceful shutdown."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    logger.info("Database schema managed by Alembic migrations")
    
    # Connect to Redis cache
    if settings.CACHE_ENABLED:
        await cache_manager.connect()
    
    logger.info(f"{settings.APP_NAME} started successfully - ready to accept requests")
    
    yield
    
    # Cleanup on shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    
    # Mark as shutting down to reject new requests
    shutdown_manager.is_shutting_down = True
    
    # Give a brief moment for active requests
    if shutdown_manager.active_requests > 0:
        logger.info(f"Waiting briefly for {shutdown_manager.active_requests} active request(s)...")
        await asyncio.sleep(2)  # Simple 2 second wait
    
    # Close cache connections
    if settings.CACHE_ENABLED:
        await cache_manager.disconnect()
    
    # Close database connections
    await dispose_engine()
    
    logger.info(f"{settings.APP_NAME} shutdown complete")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Graceful shutdown middleware (must be first to track all requests)
@app.middleware("http")
async def graceful_shutdown_middleware(request: Request, call_next):
    """Track active requests and reject new requests during shutdown."""
    # Reject new requests if shutting down
    if shutdown_manager.is_shutting_down:
        logger.warning(f"Rejecting request {request.method} {request.url.path} - service is shutting down")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "error": "SERVICE_UNAVAILABLE",
                "message": "Service is shutting down - please retry with another instance"
            },
            headers={"Retry-After": "10"}
        )
    
    # Track active request
    shutdown_manager.request_started()
    
    try:
        response = await call_next(request)
        return response
    finally:
        # Always mark request as finished, even if it failed
        shutdown_manager.request_finished()


# Request ID tracking middleware
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
    # Note: Allows CDN resources for Swagger UI docs
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net"
    )
    
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
