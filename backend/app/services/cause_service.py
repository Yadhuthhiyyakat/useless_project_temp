"""Death cause taxonomy for the Digital Cemetery.

Phase 10 formalises the previously provisional ``DELETE_DETECTED`` string into a
proper enum and centralises cause determination so later phases (trash,
overwritten, etc.) can refine it without touching lifecycle code.

Design notes
------------
* ``DeathCause`` is a ``str`` enum so its members compare equal to their raw
  string values and can be stored directly in the ``deaths.cause`` column.
* The default model value ``"Unknown"`` is preserved as ``DeathCause.UNKNOWN``
  so existing rows remain valid.
* ``determine_cause`` is intentionally small today: every confirmed deletion
  observed as a filesystem ``DELETED`` event is ``DELETE_DETECTED``.  Later
  phases will enrich it (e.g. trash vs. permanent delete) behind the same
  call-site.
"""

from __future__ import annotations

from enum import Enum

from app.database.models import File
from app.watcher.events import EventKind


class DeathCause(str, Enum):
    """Authoritative set of death causes."""

    DELETE_DETECTED = "DELETE_DETECTED"
    UNKNOWN = "Unknown"
    MISSING = "MISSING"

    @property
    def label(self) -> str:
        """Human-readable label for API responses."""
        labels = {
            DeathCause.DELETE_DETECTED: "Deleted",
            DeathCause.UNKNOWN: "Unknown",
            DeathCause.MISSING: "Missing",
        }
        return labels[self]


def determine_cause(
    *,
    event_kind: EventKind | str | None = None,
    file: File | None = None,
) -> DeathCause:
    """Classify a confirmed deletion into a :class:`DeathCause`.

    Today the watcher is the sole deletion source, so any explicit deleted
    event maps to ``DELETE_DETECTED``.  A ``None`` event (e.g. a file found
    missing on scan) maps to ``MISSING``.  Everything else falls back to
    ``UNKNOWN`` so the taxonomy stays exhaustive as new sources are added.
    """
    if event_kind is None:
        return DeathCause.MISSING
    kind_value = event_kind.value if isinstance(event_kind, Enum) else str(event_kind)
    if kind_value == EventKind.DELETED.value:
        return DeathCause.DELETE_DETECTED
    if kind_value == DeathCause.MISSING.value:
        return DeathCause.MISSING
    return DeathCause.UNKNOWN


def is_valid_cause(value: str) -> bool:
    """True when ``value`` is a member of :class:`DeathCause`."""
    return value in {member.value for member in DeathCause}