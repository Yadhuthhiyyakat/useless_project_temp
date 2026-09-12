"""File lifecycle service.

Central orchestration of a tracked file's life:

    born (CREATED / first scan)
      -> modified (MODIFIED)
      -> moved (MOVED)
      -> confirmed death (DELETED)

The rules enforced here are the heart of the backend's correctness:

* A file record is only ever mutated while it is alive. A dead record is
  permanently immutable and is never resurrected.
* A DELETED event must be *confirmed* before it becomes a death: if the path
  still holds a regular file when the event is processed, the death is
  cancelled (transient / false event) and the record is simply refreshed.
* Deaths are recorded atomically and idempotently — exactly one permanent
  death record per file — via ``DeathRepository.create_death``.

The live watcher funnels every event through this service (via the event
processor), so the whole pipeline shares one lifecycle.
"""

from __future__ import annotations

import os
import stat as stat_module
from dataclasses import dataclass
from datetime import datetime

from app.database.database import Database
from app.database.models import Death, utcnow
from app.database.repositories import DeathRepository, FileRepository
from app.logging_config import get_logger
from app.services.cause_service import DeathCause, determine_cause
from app.services.cemetery_service import coordinates_for_death
from app.services.epitaph_service import generate_epitaph
from app.services.file_registration import FileRegistrationService, RegistrationOutcome
from app.services.lifespan_service import Lifespan, birth_timestamp, compute_lifespan
from app.watcher.events import EventKind

logger = get_logger(__name__)

# Backwards-compatible alias — prefer DeathCause.DELETE_DETECTED.
DEATH_CAUSE_DELETE_DETECTED: str = DeathCause.DELETE_DETECTED.value


@dataclass
class DeathOutcome:
    """Result of attempting to confirm a deletion."""

    recorded: bool
    reason: str
    death: Death | None = None
    lifespan: Lifespan | None = None


class FileLifecycleService:
    """Owns the birth/death state machine for tracked files."""

    def __init__(
        self,
        database: Database,
        *,
        registration: FileRegistrationService | None = None,
    ) -> None:
        self.database = database
        self.registration = registration or FileRegistrationService()

    def register(
        self, path: str, *, now: datetime | None = None
    ) -> RegistrationOutcome:
        """Register or refresh a path (birth, modification, or move).

        Only alive records can be matched, so an event for a dead path starts a
        brand-new record (a new life) instead of resurrecting the old one.
        """
        with self.database.session() as session:
            return self.registration.register_path(session, path, now=now)

    def confirm_deletion(
        self, path: str, *, deleted_at: datetime | None = None
    ) -> DeathOutcome:
        """Confirm a DELETED event and, when real, record the permanent death.

        A deletion is only recorded when the path no longer holds a regular
        file at processing time. False or transient events are cancelled and
        the alive record is refreshed instead.
        """
        path = os.path.abspath(path)
        if self._regular_file_present(path):
            logger.info(
                "Deletion cancelled for %s: file still present", path
            )
            self.register(path)
            return DeathOutcome(recorded=False, reason="file_still_present")

        with self.database.session() as session:
            record = FileRepository(session).get_alive_by_path(path)
            if record is None:
                logger.info("Deletion ignored for unknown file: %s", path)
                return DeathOutcome(recorded=False, reason="unknown_file")

            delete_time = deleted_at or utcnow()
            lifespan = compute_lifespan(
                born_at=birth_timestamp(record), deleted_at=delete_time
            )
            cause = determine_cause(event_kind=EventKind.DELETED, file=record)
            cemetery_x, cemetery_y = coordinates_for_death(
                file_id=record.id, original_path=record.path
            )
            epitaph = generate_epitaph(file=record, lifespan=lifespan, cause=cause)
            death = DeathRepository(session).create_death(
                file=record,
                filename=record.filename,
                original_path=record.path,
                extension=record.extension,
                size_bytes=record.size_bytes,
                born_at=lifespan.born_at,
                last_modified_at=record.modified_at,
                deleted_at=lifespan.deleted_at,
                lifespan_seconds=lifespan.seconds,
                cause=cause.value,
                epitaph=epitaph,
                cemetery_x=cemetery_x,
                cemetery_y=cemetery_y,
            )
            logger.info("Death confirmed for %s (cause=%s)", path, cause.value)
            return DeathOutcome(
                recorded=True,
                reason="death_recorded",
                death=death,
                lifespan=lifespan,
            )

    @staticmethod
    def _regular_file_present(path: str) -> bool:
        """True when ``path`` currently resolves to a regular file."""
        try:
            st = os.lstat(path)
        except OSError:
            return False
        return stat_module.S_ISREG(st.st_mode)