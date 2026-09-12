"""Filesystem event definitions and normalization.

Watchdog produces platform-specific callback objects. The watcher normalizes
them into a single :class:`FileSystemEvent` (one of four kinds) before handing
them to the event-processing layer, so business logic never depends on watchdog
types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class EventKind(str, Enum):
    """Supported lifecycle events for tracked files."""

    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    MOVED = "MOVED"
    DELETED = "DELETED"


def utcnow() -> datetime:
    """Naive UTC now, matching the database timestamp convention."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class FileSystemEvent:
    """A normalized filesystem event ready for date processing."""

    kind: EventKind
    src_path: str
    dest_path: str | None = None
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", utcnow())

    @property
    def path(self) -> str:
        """The current path involved in the event (destination for moves)."""
        return self.dest_path or self.src_path