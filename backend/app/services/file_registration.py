"""Shared file registration service.

Both the initial scan and the live watcher must agree on how a discovered file
becomes (and stays) a database record: identity-first matching, path refresh on
move, bounded MODIFIED events, and never creating duplicates. This service
encapsulates that logic so the two entry points cannot drift apart.
"""

from __future__ import annotations

import os
import stat as stat_module
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.database.models import File, utcnow
from app.database.repositories import (
    EVENT_CREATED,
    EVENT_MODIFIED,
    EVENT_MOVED,
    EventRepository,
    FileRepository,
)
from app.logging_config import get_logger
from app.services.file_identity_service import FileIdentityService
from app.services.metadata_service import MetadataService

logger = get_logger(__name__)


@dataclass
class RegistrationOutcome:
    """Summary of registering one path against the database."""

    found: bool = False  # True when the path was a regular file.
    created: bool = False  # A brand-new file record was created.
    updated: bool = False  # An existing alive record was refreshed.
    events_added: int = 0
    error: str | None = None
    record: File | None = None


class FileRegistrationService:
    """Registers or refreshes a single file path (never following symlinks)."""

    def __init__(
        self,
        metadata: MetadataService | None = None,
        identity: FileIdentityService | None = None,
    ) -> None:
        self.metadata = metadata or MetadataService()
        self.identity = identity or FileIdentityService()

    def register_path(
        self,
        session: Session,
        path: str,
        *,
        now: datetime | None = None,
    ) -> RegistrationOutcome:
        """Register ``path`` idempotently.

        Never raises: failures are reported through ``outcome.error``. Non-regular
        files (symlinks, sockets, ...) are skipped silently.
        """
        path = os.path.abspath(path)
        meta = self.metadata.try_extract(path)
        if meta is None:
            return RegistrationOutcome(error=f"Could not stat {path}")
        try:
            is_regular = stat_module.S_ISREG(os.lstat(path).st_mode)
        except OSError:
            return RegistrationOutcome(error=f"Could not stat {path}")
        if not is_regular:
            return RegistrationOutcome()

        outcome = RegistrationOutcome(found=True)
        files = FileRepository(session)
        events = EventRepository(session)
        identity = self.identity.identity_of(path)
        existing = self.identity.match_existing_file(files, path)
        now = now if now is not None else utcnow()

        if existing is None:
            record = files.create(
                path=meta.path,
                filename=meta.filename,
                extension=meta.extension,
                size_bytes=meta.size_bytes,
                created_at=meta.created_at,
                modified_at=meta.modified_at,
                first_seen_at=now,
                last_seen_at=now,
                filesystem_id=meta.filesystem_id,
            )
            session.flush()
            events.add(
                file_id=record.id,
                event_type=EVENT_CREATED,
                timestamp=now,
                new_path=path,
            )
            outcome.created = True
            outcome.events_added = 1
            outcome.record = record
            return outcome

        size_or_mtime_changed = (
            existing.size_bytes != meta.size_bytes
            or existing.modified_at != meta.modified_at
        )
        same_physical_file = (
            identity is not None and existing.filesystem_id == identity.key
        )

        if same_physical_file and existing.path != path:
            old_path = existing.path
            existing.path = meta.path
            existing.filename = meta.filename
            existing.extension = meta.extension
            events.add(
                file_id=existing.id,
                event_type=EVENT_MOVED,
                timestamp=now,
                old_path=old_path,
                new_path=path,
            )
            outcome.events_added = 1
        elif size_or_mtime_changed:
            events.add(
                file_id=existing.id,
                event_type=EVENT_MODIFIED,
                timestamp=now,
                new_path=path,
            )
            outcome.events_added = 1

        files.update_from_scan(
            existing,
            size_bytes=meta.size_bytes,
            modified_at=meta.modified_at,
            last_seen_at=now,
        )
        outcome.updated = True
        outcome.record = existing
        return outcome