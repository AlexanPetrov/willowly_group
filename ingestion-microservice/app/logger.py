"""Centralized logging configuration for Ingestion Microservice with structured logging and operation IDs."""

import logging
import sys
import json
import uuid
import contextvars
from datetime import datetime, timezone
from typing import Optional
from config import settings


# Context variable for operation ID (trace ID)
operation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "operation_id", default=None
)


def set_operation_id(op_id: Optional[str] = None) -> str:
    """Set or generate an operation ID for this context.
    
    Args:
        op_id: Optional operation ID string. If None, generates a UUID.
        
    Returns:
        The operation ID that was set.
    """
    if op_id is None:
        op_id = str(uuid.uuid4())
    operation_id_ctx.set(op_id)
    return op_id


def get_operation_id() -> Optional[str]:
    """Get the current operation ID from context."""
    return operation_id_ctx.get()


class StructuredFormatter(logging.Formatter):
    """Base formatter for structured logging."""
    
    def add_operation_id(self, record: logging.LogRecord) -> None:
        """Add operation ID to log record."""
        record.operation_id = get_operation_id() or "N/A"


class JSONFormatter(StructuredFormatter):
    """JSON formatter with operation IDs and structured context."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        self.add_operation_id(record)
        
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
            "operation_id": record.operation_id,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["context"] = record.extra_data
        
        return json.dumps(log_data)


class ConsoleFormatter(StructuredFormatter):
    """Console formatter with operation IDs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console."""
        self.add_operation_id(record)
        
        base = (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} "
            f"{record.levelname:<8s} "
            f"[{record.operation_id}] "
            f"[{record.name}] "
            f"{record.getMessage()}"
        )
        
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        
        return base


def setup_logger() -> logging.Logger:
    """Configure and return application logger with structured logging and operation IDs."""
    logger = logging.getLogger("ingestion_microservice")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    
    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if settings.LOG_FILE:
        try:
            file_handler = logging.FileHandler(settings.LOG_FILE)
            
            if settings.LOG_FORMAT == "json":
                file_handler.setFormatter(JSONFormatter())
            else:
                file_handler.setFormatter(ConsoleFormatter())
            
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to create file handler for {settings.LOG_FILE}: {e}")
    
    return logger


logger = setup_logger()


class LogContext:
    """Context manager for operation IDs and structured logging."""
    
    def __init__(self, op_id: Optional[str] = None):
        """Initialize with optional operation ID."""
        self.op_id = op_id
        self.token = None
    
    def __enter__(self) -> str:
        """Enter context and set operation ID."""
        self.op_id = set_operation_id(self.op_id)
        return self.op_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass

