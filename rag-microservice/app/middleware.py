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
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            "[%s] Rejecting %s %s - service is shutting down",
            request_id, request.method, request.url.path
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
    logger.info("[%s] %s %s - Request received", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(
            "[%s] %s %s - Status: %d - Duration: %.3fs",
            request_id, request.method, request.url.path, response.status_code, duration
        )
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] %s %s - Error: %s - Duration: %.3fs",
            request_id, request.method, request.url.path, str(e), duration,
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
