"""Metadata extraction service.

Extracts on-disk metadata for tracked files WITHOUT ever reading file contents.
Only ``os.stat``-style system calls are used; files are never opened for reading
or indexed in any way. This is a metadata tracker, not a content indexer.

Platform notes on creation time:

* Windows — ``st_ctime`` is the file creation time.
* macOS / BSD — ``st_birthtime`` (when present) is the creation time.
* Linux — there is no portable creation-time field. ``st_ctime`` is the inode
  *change* time, NOT creation time, so it is deliberately NOT reported as the
  creation time. On Linux ``created_at`` is ``None`` and callers must fall back
  to the first-seen timestamp (stored by the scan/watcher layers).

Symlinks are never followed (``lstat``), matching the privacy rule that the
monitor must not cross configured monitoring boundaries.

``first_seen_at`` / ``last_seen_at`` are NOT part of the stat payload: they are
system timestamps assigned by the scan and event-processing layers when the
backend itself records a file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_naive_from_timestamp(timestamp: float) -> datetime:
    """Convert a POSIX timestamp to a naive UTC datetime for storage."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)


def extension_of(filename: str) -> str:
    """Return the extension including the leading dot (``""`` if none).

    A leading-dot filename such as ``.bashrc`` has no extension: Python's
    ``os.path.splitext`` follows that convention.
    """
    _, extension = os.path.splitext(filename)
    return extension


def filesystem_id_of(st: os.stat_result) -> str | None:
    """Build a stable filesystem identity from a stat result.

    Returns ``"device:inode"`` where both are non-zero, otherwise ``None``
    (e.g. virtual filesystems that expose no real inode). The dedicated file
    identity service builds on this in a later phase.
    """
    if st.st_dev and st.st_ino:
        return f"{st.st_dev}:{st.st_ino}"
    return None


@dataclass(frozen=True)
class FileMetadata:
    """Stat-only metadata describing a file at an instant in time."""

    path: str
    filename: str
    extension: str
    size_bytes: int
    created_at: datetime | None
    modified_at: datetime | None
    filesystem_id: str | None


class MetadataService:
    """Stat-only metadata extraction for filesystem paths."""

    @staticmethod
    def _creation_time(st: os.stat_result) -> datetime | None:
        """Best-effort creation timestamp per platform (never ``st_ctime`` on POSIX)."""
        if os.name == "nt":
            # On Windows st_ctime IS the creation time.
            return _utc_naive_from_timestamp(st.st_ctime)
        birthtime = getattr(st, "st_birthtime", None)
        if birthtime is not None:
            return _utc_naive_from_timestamp(birthtime)
        return None

    def extract(self, path: str) -> FileMetadata:
        """Extract metadata for an existing path.

        Raises:
            OSError: if the path does not exist or cannot be stat-ed.
        """
        st = os.lstat(path)
        return self._from_stat(path, st)

    def try_extract(self, path: str) -> FileMetadata | None:
        """Like :meth:`extract` but returns ``None`` on any failure.

        Useful when a watcher event references a path that may already be gone.
        """
        try:
            return self.extract(path)
        except OSError:
            return None

    @classmethod
    def _from_stat(cls, path: str, st: os.stat_result) -> FileMetadata:
        filename = os.path.basename(path)
        return FileMetadata(
            path=os.path.abspath(path),
            filename=filename,
            extension=extension_of(filename),
            size_bytes=st.st_size,
            created_at=cls._creation_time(st),
            modified_at=_utc_naive_from_timestamp(st.st_mtime),
            filesystem_id=filesystem_id_of(st),
        )