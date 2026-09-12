"""Filesystem event processor — the watcher's thin entry point.

Watchdog callbacks never perform business logic directly: the watcher's event
handler normalizes a filesystem event and hands it to this processor, which
applies ignore rules and dispatches to the shared file lifecycle service.

Phase 7 funnelled every event through the shared registration service; Phase 8
moved the full state machine (including death confirmation) into
:class:`~app.services.file_lifecycle.FileLifecycleService`. The processor keeps
only the rules that are specific to events: which paths to ignore and which
lifecycle action each event kind triggers.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime

from app.database.database import Database
from app.logging_config import get_logger
from app.services.file_lifecycle import (
    DEATH_CAUSE_DELETE_DETECTED as CAUSE_DELETE_DETECTED,  # re-export for tests
    FileLifecycleService,
)
from app.services.paths import database_file_paths, path_is_under_ignored
from app.services.security import SecurityError, resolve_within_roots
from app.watcher.events import EventKind, FileSystemEvent

logger = get_logger(__name__)


class EventProcessor:
    """Consumes normalized filesystem events and drives the file lifecycle."""

    def __init__(
        self,
        database: Database,
        *,
        ignored_directories: Iterable[str] = (),
        watched_directories: Iterable[str] = (),
        lifecycle: FileLifecycleService | None = None,
    ) -> None:
        self.database = database
        self.lifecycle = lifecycle or FileLifecycleService(database)
        self._ignored = {
            os.path.abspath(path) for path in ignored_directories if path
        }
        # Backend DB sidecars are always excluded from tracking.
        self._ignored |= database_file_paths(database.config.database_url)
        # Security roots: watched directories (resolved)
        self._roots = [os.path.abspath(d) for d in watched_directories if d]

    def is_ignored(self, path: str) -> bool:
        """True when a path is ignored or belongs to the backend's own database."""
        return path_is_under_ignored(os.path.abspath(path), self._ignored)

    def _validate_path(self, path: str) -> str | None:
        """Validate path against security roots. Returns resolved path or None if invalid."""
        if not self._roots:
            logger.warning("No watched directories configured; skipping path %s", path)
            return None
        try:
            resolved = resolve_within_roots(path, self._roots)
            return str(resolved)
        except SecurityError as e:
            logger.warning("Security check failed for %s: %s (code=%s)", path, e, e.code)
            return None

    def is_ignored(self, path: str) -> bool:
        """True when a path is ignored or belongs to the backend's own database."""
        return path_is_under_ignored(os.path.abspath(path), self._ignored)

    def process(self, event: FileSystemEvent) -> None:
        """Apply a single normalized event to the file lifecycle."""
        if event.kind in (EventKind.CREATED, EventKind.MODIFIED, EventKind.MOVED):
            self._register(event.path)
        elif event.kind is EventKind.DELETED:
            self._delete(event.path, event.timestamp)
        else:
            logger.warning("Unknown event kind: %r", event.kind)

    def _register(self, path: str) -> None:
        if not path or self.is_ignored(path):
            logger.debug("Event ignored for path: %s", path)
            return
        safe = self._validate_path(path)
        if safe is None:
            return
        outcome = self.lifecycle.register(safe)
        if outcome.error is not None:
            logger.info("Could not register %s: %s", safe, outcome.error)
        elif outcome.created:
            logger.info("Registered new file: %s", safe)

    def _delete(self, path: str, deleted_at: datetime | None) -> None:
        if not path or self.is_ignored(path):
            logger.debug("Delete ignored for path: %s", path)
            return
        safe = self._validate_path(path)
        if safe is None:
            return
        outcome = self.lifecycle.confirm_deletion(safe, deleted_at=deleted_at)
        if outcome.recorded:
            logger.info("Death recorded for %s (cause=%s)", safe, CAUSE_DELETE_DETECTED)