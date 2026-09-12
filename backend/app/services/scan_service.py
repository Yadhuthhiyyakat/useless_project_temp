"""Initial directory scan service.

Recursively discovers existing files inside a configured directory, extracts
their metadata (stat only, never file contents), and registers them with the
database. The scan is safe to run repeatedly:

    scan(scan(scan(directory)))

must not create duplicate file records or duplicate CREATED events.

Matching uses the identity service first and the path as a fallback, so a file
that was renamed between scans keeps its single record (the path is refreshed
and a MOVED event is recorded). Files that already exist keep their records;
only unknown files get a CREATED event. Changes in size or mtime trigger a
bounded MODIFIED event.

The per-file registration behaviour is shared with the live watcher through
:class:`~app.services.file_registration.FileRegistrationService`, so scans and
watcher events cannot drift apart.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.database.database import Database
from app.logging_config import get_logger
from app.services.file_identity_service import FileIdentityService
from app.services.file_registration import FileRegistrationService
from app.services.metadata_service import MetadataService
from app.services.paths import database_file_paths, path_is_under_ignored

logger = get_logger(__name__)


@dataclass
class ScanResult:
    """Summary of one directory scan."""

    directory: str
    files_found: int = 0
    files_created: int = 0
    files_updated: int = 0
    events_added: int = 0
    errors: list[str] = field(default_factory=list)


class ScanService:
    """Scans directories and registers discovered files."""

    def __init__(
        self,
        database: Database,
        metadata: MetadataService | None = None,
        identity: FileIdentityService | None = None,
        registration: FileRegistrationService | None = None,
    ) -> None:
        self.database = database
        self.metadata = metadata or MetadataService()
        self.identity = identity or FileIdentityService()
        self.registration = registration or FileRegistrationService(
            metadata=self.metadata, identity=self.identity
        )

    def scan_directory(
        self,
        directory: str,
        *,
        ignored_directories: Iterable[str] = (),
    ) -> ScanResult:
        """Scan ``directory`` recursively and register discovered files.

        Args:
            directory: Root of the directory to monitor.
            ignored_directories: Absolute paths to skip (pruned from the walk).

        Returns:
            A :class:`ScanResult` with per-file counters. Per-file stat errors
            are collected in ``result.errors`` and do not abort the scan.
        """
        root = os.path.abspath(directory)
        result = ScanResult(directory=root)
        ignored = {os.path.abspath(path) for path in ignored_directories}
        # The application must never track its own SQLite database files.
        ignored.update(self._database_file_paths())

        if path_is_under_ignored(root, ignored):
            logger.info("Scan of %s skipped: directory is ignored", root)
            return result
        if not os.path.isdir(root):
            message = f"Scan target is not a directory: {root}"
            result.errors.append(message)
            logger.warning(message)
            return result

        logger.info("Scan start: %s (ignored: %s)", root, sorted(ignored))
        with self.database.session() as session:
            for dirpath, dirnames, filenames in os.walk(
                root, followlinks=False, onerror=_walk_error_factory(result)
            ):
                dirnames[:] = [
                    dirname
                    for dirname in dirnames
                    if not path_is_under_ignored(
                        os.path.join(dirpath, dirname), ignored
                    )
                ]

                for name in sorted(filenames):
                    path = os.path.abspath(os.path.join(dirpath, name))
                    if path_is_under_ignored(path, ignored):
                        continue
                    self._register_file(session, path, result)

        logger.info(
            "Scan end: %s -> %d files, %d created, %d updated, %d events, %d errors",
            root,
            result.files_found,
            result.files_created,
            result.files_updated,
            result.events_added,
            len(result.errors),
        )
        return result

    def _database_file_paths(self) -> set[str]:
        """Absolute paths of the backend's own SQLite database sidecars."""
        return database_file_paths(self.database.config.database_url)

    def _register_file(self, session, path: str, result: ScanResult) -> None:
        """Register one discovered path and fold its outcome into the result."""
        outcome = self.registration.register_path(session, path)
        if outcome.error is not None:
            result.errors.append(outcome.error)
            return
        if not outcome.found:
            return
        result.files_found += 1
        if outcome.created:
            result.files_created += 1
        if outcome.updated:
            result.files_updated += 1
        result.events_added += outcome.events_added


def _walk_error_factory(result: ScanResult):
    def _onerror(error: OSError) -> None:
        message = str(error)
        result.errors.append(message)
        logger.warning("Scan walk error: %s", message)

    return _onerror