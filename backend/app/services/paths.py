"""Shared filesystem path helpers used by scan and watcher registration."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url


DEFAULT_IGNORED_DIR_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".cache",
    ".next",
    ".turbo",
}


def path_is_under_ignored(path: str, ignored: set[str]) -> bool:
    """Return True when ``path`` equals an ignored dir or lives beneath one."""
    if any(
        path == ignored_dir or path.startswith(ignored_dir + os.sep)
        for ignored_dir in ignored
    ):
        return True

    try:
        parts = Path(path).parts
        if any(part in DEFAULT_IGNORED_DIR_NAMES for part in parts):
            return True
    except Exception:
        pass

    return False


def database_file_paths(database_url: str) -> set[str]:
    """Absolute paths of the SQLite database and its sidecars.

    These must never be monitored: the backend must not track its own state.
    """
    url = make_url(database_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or not database or database == ":memory:":
        return set()
    db_path = Path(database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path = db_path.expanduser().resolve()
    return {
        str(db_path),
        str(db_path) + "-wal",
        str(db_path) + "-shm",
        str(db_path) + "-journal",
    }