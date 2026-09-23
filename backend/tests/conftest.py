"""Shared pytest fixtures.

Every test uses a fresh SQLite database inside a temporary directory. Tests
never touch real user directories.
"""

from __future__ import annotations

import os
import pytest

for key in [
    "CORS_ORIGINS",
    "WATCHED_DIRECTORIES",
    "IGNORED_DIRECTORIES",
    "AI_EPITAPHS_ENABLED",
    "DATABASE_URL",
]:
    os.environ.pop(key, None)

from app.config import Config
from app.database.database import Database


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch, tmp_path_factory):
    """Ensure local developer .env files do not leak into unit tests."""
    empty_dir = tmp_path_factory.mktemp("clean_env")
    monkeypatch.setattr("app.config.BASE_DIR", empty_dir)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("WATCHED_DIRECTORIES", raising=False)
    monkeypatch.delenv("IGNORED_DIRECTORIES", raising=False)
    monkeypatch.delenv("AI_EPITAPHS_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)



@pytest.fixture
def db_config(tmp_path):
    """A Config pointed at a throwaway SQLite file."""
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'test.db'}"
    return config


@pytest.fixture
def database(db_config):
    """An initialized, isolated Database instance."""
    db = Database(db_config)
    db.init()
    try:
        yield db
    finally:
        db.drop_all()
        db.dispose()


@pytest.fixture
def app(tmp_path):
    """A configured FastAPI app backed by a throwaway database."""
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'app_test.db'}"
    from app.main import create_app

    return create_app(config)