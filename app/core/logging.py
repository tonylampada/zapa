"""Logging configuration for Zapa applications."""

import logging
import logging.config
import sys
from typing import Any

from app.config.base import BaseSettings


def setup_logging(settings: BaseSettings) -> None:
    """Set up logging configuration."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": (
                    "%(asctime)s - %(name)s - %(levelname)s - "
                    "%(filename)s:%(lineno)d - %(funcName)s - %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": (
                    "%(asctime)s - %(name)s - %(levelname)s - "
                    "%(filename)s:%(lineno)d - %(funcName)s - %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "detailed" if settings.DEBUG else "default",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    # Use JSON formatter in production
    if settings.ENVIRONMENT == "production":
        logging_config["handlers"]["console"]["formatter"] = "json"

    logging.config.dictConfig(logging_config)

    # Set up exception logging
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger = logging.getLogger(__name__)
        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception
