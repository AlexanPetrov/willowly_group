from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logger import logger
from app.routes import router
from app.middleware import (
    graceful_shutdown_middleware,
    add_request_id_middleware,
    request_logging_middleware,
    security_headers_middleware,
    set_shutdown_manager,
)
from app.monitoring import setup_monitoring


class GracefulShutdownManager:
    def __init__(self):
        self.is_shutting_down = False
        self.active_requests = 0
        self.shutdown_timeout = settings.GRACEFUL_SHUTDOWN_TIMEOUT

    def request_started(self):
        if not self.is_shutting_down:
            self.active_requests += 1

    def request_finished(self):
        self.active_requests -= 1


shutdown_manager = GracefulShutdownManager()
set_shutdown_manager(shutdown_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    logger.info("RAG Service startup complete")
    try:
        yield
    finally:
        shutdown_manager.is_shutting_down = True
        logger.info("RAG Service shutdown complete")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Middleware (outermost first)
app.middleware("http")(graceful_shutdown_middleware)
app.middleware("http")(add_request_id_middleware)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(security_headers_middleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monitoring
setup_monitoring(app)


@app.get("/", tags=["meta"])
def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": settings.APP_NAME,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "api_prefix": "/api",
        }
    )


# API routes
app.include_router(router, prefix="/api")
