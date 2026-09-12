"""Shared pytest fixtures.

Every test uses a fresh SQLite database inside a temporary directory. Tests
never touch real user directories.
"""

from __future__ import annotations

import pytest

from app.config import Config
from app.database.database import Database


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