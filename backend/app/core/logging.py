import logging
from logging.config import dictConfig
from typing import Dict, Any

def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "formatter": "detailed",
                "class": "logging.FileHandler",
                "filename": "/var/log/app/backend.log",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": level,
                "propagate": True,
            },
        },
    }
    dictConfig(log_config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
