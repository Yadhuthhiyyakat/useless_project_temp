"""SQLite database engine and session management.

The ``Database`` class owns the engine and a thread-safe session factory.
Each watcher thread and each FastAPI request gets its own session via the
``session()`` context manager, which commits on success and rolls back on
any exception so operations are kept transactional.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Config
from app.database.models import Base
from app.logging_config import get_logger

logger = get_logger(__name__)


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Apply per-connection SQLite pragmas for safety and concurrency."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Database:
    """Owns the SQLAlchemy engine and session factory for the application."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.engine = self._build_engine()
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def _is_sqlite(self) -> bool:
        return make_url(self.config.database_url).get_backend_name() == "sqlite"

    def _build_engine(self) -> Engine:
        url = make_url(self.config.database_url)
        kwargs: dict = {"echo": False}

        if self._is_sqlite():
            # Watcher threads and FastAPI workers share sessions concurrently.
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if url.database == ":memory:":
                kwargs["poolclass"] = StaticPool
                kwargs["connect_args"] = {"check_same_thread": False}

        engine = create_engine(url, **kwargs)
        if self._is_sqlite():
            event.listen(engine, "connect", _configure_sqlite_connection)

        return engine

    def init(self) -> None:
        """Create the database file, parent directory, and all tables."""
        if self._is_sqlite():
            url = make_url(self.config.database_url)
            if url.database and url.database != ":memory:":
                database_path = Path(url.database)
                if not database_path.is_absolute():
                    database_path = Path.cwd() / database_path
                database_path.expanduser().resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )
        Base.metadata.create_all(self.engine)
        logger.info("Database initialized at %s", self.config.database_url)

    def drop_all(self) -> None:
        """Drop every table. Intended for tests only."""
        Base.metadata.drop_all(self.engine)

    def dispose(self) -> None:
        """Release the connection pool. Useful at shutdown / end of tests."""
        self.engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session scoped to a transaction.

        Commits on successful exit; rolls back and re-raises on any exception.
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()