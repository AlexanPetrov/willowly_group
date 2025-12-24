"""FastAPI application entry point with lifecycle management."""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio

from .config import settings
from .routes import router
from .db import dispose_engine
from .cache import cache_manager
from .logger import logger
from .middleware import (
    graceful_shutdown_middleware,
    add_request_id_middleware,
    request_logging_middleware,
    security_headers_middleware,
    set_shutdown_manager,
)
from .monitoring import setup_monitoring

# ==================== Rate Limiting ====================

limiter = Limiter(key_func=get_remote_address)

# ==================== Graceful Shutdown ====================


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
                await asyncio.sleep(0.1)
            
            if self.active_requests == 0:
                logger.info("All active requests completed successfully")
        else:
            logger.info("No active requests - proceeding with immediate shutdown")


shutdown_manager = GracefulShutdownManager()
set_shutdown_manager(shutdown_manager)

# ==================== Application Lifecycle ====================


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
    
    shutdown_manager.is_shutting_down = True
    
    if shutdown_manager.active_requests > 0:
        logger.info(f"Waiting briefly for {shutdown_manager.active_requests} active request(s)...")
        await asyncio.sleep(2)
    
    if settings.CACHE_ENABLED:
        await cache_manager.disconnect()
    
    await dispose_engine()
    
    logger.info(f"{settings.APP_NAME} shutdown complete")

# ==================== Application Setup ====================


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Middleware registration (first registered = outermost layer)
app.middleware("http")(graceful_shutdown_middleware)
app.middleware("http")(add_request_id_middleware)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(security_headers_middleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include API routes
app.include_router(router)

# Setup Prometheus monitoring
setup_monitoring(app)
