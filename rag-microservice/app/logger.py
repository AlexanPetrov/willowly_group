"""Centralized logging configuration for the RAG microservice."""

import logging
import sys
from .config import settings


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("rag_microservice")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
