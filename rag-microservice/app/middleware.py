"""HTTP middleware for request handling, logging, and security (aligned with user-microservice)."""

from fastapi import Request
from fastapi.responses import JSONResponse
import time
import uuid
from .config import settings
from .logger import logger


shutdown_manager = None


def set_shutdown_manager(manager):
    global shutdown_manager
    shutdown_manager = manager


async def graceful_shutdown_middleware(request: Request, call_next):
    if shutdown_manager and shutdown_manager.is_shutting_down:
        logger.warning(
            f"Rejecting request {request.method} {request.url.path} - service is shutting down"
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": "SERVICE_UNAVAILABLE",
                "message": "Service is shutting down - please retry with another instance",
            },
            headers={"Retry-After": "10"},
        )

    if shutdown_manager:
        shutdown_manager.request_started()

    try:
        response = await call_next(request)
        return response
    finally:
        if shutdown_manager:
            shutdown_manager.request_finished()


async def add_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def request_logging_middleware(request: Request, call_next):
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] {request.method} {request.url.path} - Request received")
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Duration: {duration:.3f}s"
        )
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} - Error: {str(e)} - Duration: {duration:.3f}s",
            exc_info=True,
        )
        raise


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response
