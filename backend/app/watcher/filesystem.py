"""Filesystem watcher.

Manages watchdog observers for the user-configured directories. Only the
directories explicitly configured are monitored — the entire filesystem is
never watched by default.

Watchdog callbacks are intentionally thin: :class:`FileEventHandler` only
normalizes an event and forwards it to the event-processing layer.
"""

from __future__ import annotations

import os

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.logging_config import get_logger
from app.watcher.events import EventKind, FileSystemEvent
from app.watcher.processor import EventProcessor

logger = get_logger(__name__)


class WatcherError(Exception):
    """Raised for invalid watcher configuration (e.g. a non-directory path)."""


class FileEventHandler(FileSystemEventHandler):
    """Normalizes watchdog callbacks into :class:`FileSystemEvent` objects.

    Directory-level events are filtered out: file-level events that watchdogs
    emit for recursive watches are sufficient for the backend's purposes.
    """

    def __init__(self, processor: EventProcessor) -> None:
        self._processor = processor

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._emit(EventKind.CREATED, event.src_path, None)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._emit(EventKind.MODIFIED, event.src_path, None)

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._emit(EventKind.MOVED, event.src_path, event.dest_path)

    def on_deleted(self, event) -> None:
        if event.is_directory:
            return
        self._emit(EventKind.DELETED, event.src_path, None)

    def _emit(
        self,
        kind: EventKind,
        src_path: str,
        dest_path: str | None,
    ) -> None:
        self._processor.process(
            FileSystemEvent(
                kind=kind,
                src_path=src_path,
                dest_path=dest_path,
            )
        )


class WatcherService:
    """Owns a watchdog ``Observer`` watching multiple user directories."""

    def __init__(self, handler: FileSystemEventHandler) -> None:
        self._handler = handler
        self._observer = Observer(timeout=0.5)
        self._watched: dict[str, object] = {}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def watched_directories(self) -> list[str]:
        return sorted(self._watched)

    def add_directory(self, directory: str, *, recursive: bool = True) -> None:
        """Start (or mark for) watching a directory.

        Args:
            directory: Absolute path of the directory to monitor.
            recursive: Watch subdirectories too.

        Raises:
            WatcherError: if the path is not an existing directory.
        """
        path = os.path.abspath(directory)
        if not os.path.isdir(path):
            raise WatcherError(f"Not an existing directory: {path}")
        if path in self._watched:
            return
        self._watched[path] = self._observer.schedule(
            self._handler, path, recursive=recursive
        )
        logger.info("Watching directory: %s", path)

    def remove_directory(self, directory: str) -> None:
        """Stop watching a directory, ignoring paths that are not watched."""
        path = os.path.abspath(directory)
        watch = self._watched.pop(path, None)
        if watch is not None:
            self._observer.unschedule(watch)
            logger.info("Stopped watching directory: %s", path)

    def start(self) -> None:
        """Start the observer thread. Idempotent."""
        if self._running:
            return
        if not self._watched:
            logger.warning("Watcher starting with no directories configured")
        self._observer.start()
        self._running = True
        logger.info(
            "Filesystem watcher started (%d directories)",
            len(self._watched),
        )

    def stop(self) -> None:
        """Stop the observer thread and wait for a clean shutdown."""
        if not self._running:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._running = False
        logger.info("Filesystem watcher stopped")

    def status(self) -> dict:
        """Current watcher state used by the status endpoint (later phase)."""
        return {
            "running": self._running,
            "watched_directories": self.watched_directories,
        }