"""Logging configuration for the Digital Cemetery backend.

Logs go to the console by default. Never log file contents, API secrets or
AI provider keys.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from app.config import Config

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

LOG_FORMAT_JSON = "%(message)s"

_configured: bool = False


class JSONFormatter(logging.Formatter):
    """JSON log formatter with request_id correlation."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(config: Config, force: bool = False) -> None:
    """Configure root logging once per process.

    Args:
        config: Application configuration (uses ``log_level`` and ``log_format``).
        force: Reconfigure even if logging was already set up.
    """
    global _configured
    if _configured and not force:
        return

    level = getattr(logging, config.log_level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler: logging.Handler = logging.StreamHandler(sys.stdout)
    if getattr(config, "log_format", "text") == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)

    # Quiet down overly chatty third-party libraries to WARNING.
    for noisy in ("watchdog", "urllib3", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with the standard format applied."""
    return logging.getLogger(name)