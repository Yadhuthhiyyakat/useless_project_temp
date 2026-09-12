"""Configuration management for the Digital Cemetery backend.

Configuration is loaded from environment variables, optionally seeded by a
``.env`` file living in the project root (next to this package). Defaults are
applied for every setting so the application can boot without configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "cemetery.db"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    """Application configuration.

    Attributes:
        database_url: SQLAlchemy database URL.
        cors_origins: Allowed CORS origins (e.g. the separate frontend).
        ai_epitaphs_enabled: Whether AI epitaph generation is enabled.
        log_level: Root logging level.
        watched_directories: Extra directories to monitor (pre-configuration).
        ignored_directories: Directories to always skip while monitoring.
    """

    def __init__(self, env_file: str | Path | None = None) -> None:
        load_dotenv(env_file or BASE_DIR / ".env")

        self.database_url: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}"
        )
        self.cors_origins: list[str] = _parse_list(os.getenv("CORS_ORIGINS"))
        self.ai_epitaphs_enabled: bool = _parse_bool(
            os.getenv("AI_EPITAPHS_ENABLED"), default=False
        )
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_format: str = os.getenv("LOG_FORMAT", "text").lower()
        self.watched_directories: list[str] = _parse_list(
            os.getenv("WATCHED_DIRECTORIES")
        )
        self.ignored_directories: list[str] = _parse_list(
            os.getenv("IGNORED_DIRECTORIES")
        )


#: Convenience helper: a fresh default configuration instance.
default_config = Config()