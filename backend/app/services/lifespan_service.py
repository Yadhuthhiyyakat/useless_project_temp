"""Lifespan computation for death records.

A file's lifespan runs from its authoritative birth timestamp to the moment its
deletion was confirmed. Birth is the platform creation time when one is
available (``created_at`` from stat — Windows birthtime or macOS/BSD
``st_birthtime``); otherwise the backend's own first-seen timestamp is used
(Linux exposes no portable creation time, so ``created_at`` is ``None`` there).

Death records store the exact timestamps and the total seconds. The
human-readable label is derived at read time for API responses — it is never
persisted, so a formatting change never requires a migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.database.models import File


@dataclass(frozen=True)
class Lifespan:
    """A computed lifespan for a death record."""

    born_at: datetime
    deleted_at: datetime
    seconds: int

    @property
    def label(self) -> str:
        """Human-readable duration, e.g. ``"3 minutes"``."""
        return humanize_lifespan(self.seconds)


def birth_timestamp(record: File) -> datetime:
    """Authoritative birth time: platform creation time, else first-seen."""
    return record.created_at or record.first_seen_at


def compute_lifespan(*, born_at: datetime, deleted_at: datetime) -> Lifespan:
    """Compute the lifespan between two naive UTC timestamps.

    The duration is floored to whole seconds and never negative, so a death
    reported earlier than the recorded birth still yields ``0 seconds``.
    """
    seconds = max(0, int((deleted_at - born_at).total_seconds()))
    return Lifespan(born_at=born_at, deleted_at=deleted_at, seconds=seconds)


def humanize_lifespan(seconds: int) -> str:
    """Format a duration using its largest whole unit, with pluralisation.

    Examples: ``"0 seconds"``, ``"1 second"``, ``"3 minutes"``,
    ``"2 hours"``, ``"5 days"``.
    """
    seconds = max(0, seconds)
    if seconds < 60:
        unit, value = "second", seconds
    elif seconds < 3600:
        unit, value = "minute", seconds // 60
    elif seconds < 86400:
        unit, value = "hour", seconds // 3600
    else:
        unit, value = "day", seconds // 86400
    plural = "" if value == 1 else "s"
    return f"{value} {unit}{plural}"