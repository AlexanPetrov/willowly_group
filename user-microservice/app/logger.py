"""Centralized logging configuration for the application."""

import logging
import sys
from .config import settings


def setup_logger() -> logging.Logger:
    """Configure and return application logger with console and optional file handlers."""
    logger = logging.getLogger("user_microservice")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if settings.LOG_FILE:
        try:
            file_handler = logging.FileHandler(settings.LOG_FILE)
            if settings.LOG_FORMAT == "json":
                import json
                from datetime import datetime
                
                class JSONFormatter(logging.Formatter):
                    def format(self, record):
                        log_data = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "level": record.levelname,
                            "logger": record.name,
                            "message": record.getMessage(),
                            "module": record.module,
                            "function": record.funcName,
                            "line": record.lineno,
                        }
                        if record.exc_info:
                            log_data["exception"] = self.formatException(record.exc_info)
                        return json.dumps(log_data)
                
                file_handler.setFormatter(JSONFormatter())
            else:
                file_handler.setFormatter(console_format)
            
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to create file handler for {settings.LOG_FILE}: {e}")
    
    return logger


logger = setup_logger()
