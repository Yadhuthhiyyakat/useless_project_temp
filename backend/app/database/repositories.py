"""Repository layer: thin persistence helpers around the ORM models.

Repositories contain no business rules; they only translate between ORM models
and persistence operations. Business logic lives in the service layer.

``DeathRepository.create_death`` is the one exception-shaped method: it performs
the required atomic multi-row write (death + mark file dead + DELETED event) in
the caller's transaction and is idempotent per file.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Death, File, FileEvent, Setting, utcnow

# Event types stored in the database.
EVENT_CREATED = "CREATED"
EVENT_MODIFIED = "MODIFIED"
EVENT_MOVED = "MOVED"
EVENT_DELETED = "DELETED"

# Well-known settings keys.
SETTING_WATCHED_DIRECTORIES = "watched_directories"
SETTING_IGNORED_DIRECTORIES = "ignored_directories"
SETTING_AI_EPITAPHS_ENABLED = "ai_epitaphs_enabled"


class FileRepository:
    """Persistence for :class:`~app.database.models.File` records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, file_id: int) -> File | None:
        return self.session.get(File, file_id)

    def get_alive_by_path(self, path: str) -> File | None:
        """Return the most recent alive record for an exact path, if any."""
        stmt = (
            select(File)
            .where(File.path == path, File.is_alive.is_(True))
            .order_by(File.id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_latest_by_path(self, path: str) -> File | None:
        """Return the most recent record for an exact path (any state)."""
        stmt = (
            select(File).where(File.path == path).order_by(File.id.desc()).limit(1)
        )
        return self.session.scalar(stmt)

    def get_by_filesystem_id(self, filesystem_id: str) -> File | None:
        """Return the most recent record for a stable filesystem identity."""
        stmt = (
            select(File)
            .where(File.filesystem_id == filesystem_id)
            .order_by(File.id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_alive_by_filesystem_id(self, filesystem_id: str) -> File | None:
        """Return the most recent ALIVE record for a stable filesystem identity.

        Only alive records are considered so that an inode reused after a
        deletion cannot silently resurrect a dead file record.
        """
        stmt = (
            select(File)
            .where(
                File.filesystem_id == filesystem_id,
                File.is_alive.is_(True),
            )
            .order_by(File.id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list_alive(self) -> list[File]:
        stmt = select(File).where(File.is_alive.is_(True)).order_by(File.id)
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        path: str,
        filename: str,
        extension: str,
        size_bytes: int,
        created_at: datetime | None,
        modified_at: datetime | None,
        first_seen_at: datetime,
        last_seen_at: datetime,
        filesystem_id: str | None,
    ) -> File:
        now = utcnow()
        record = File(
            path=path,
            filename=filename,
            extension=extension,
            size_bytes=size_bytes,
            created_at=created_at,
            modified_at=modified_at,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            filesystem_id=filesystem_id,
            is_alive=True,
            created_record_at=now,
        )
        self.session.add(record)
        return record

    def update_from_scan(
        self,
        record: File,
        *,
        size_bytes: int,
        modified_at: datetime | None,
        last_seen_at: datetime,
    ) -> None:
        """Refresh live metadata observed during a scan or MODIFIED event."""
        record.size_bytes = size_bytes
        if modified_at is not None:
            record.modified_at = modified_at
        record.last_seen_at = max(record.last_seen_at, last_seen_at)


class DeathRepository:
    """Persistence for :class:`~app.database.models.Death` records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, death_id: int) -> Death | None:
        return self.session.get(Death, death_id)

    def find_by_file_id(self, file_id: int) -> Death | None:
        stmt = (
            select(Death)
            .where(Death.file_id == file_id)
            .order_by(Death.id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Death)) or 0)

    def list(self, *, limit: int = 20, offset: int = 0) -> list[Death]:
        stmt = (
            select(Death)
            .order_by(Death.deleted_at.desc(), Death.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def create_death(
        self,
        *,
        file: File,
        filename: str,
        original_path: str,
        extension: str,
        size_bytes: int,
        born_at: datetime,
        last_modified_at: datetime | None,
        deleted_at: datetime,
        lifespan_seconds: int,
        cause: str,
        epitaph: str | None,
        cemetery_x: float,
        cemetery_y: float,
    ) -> Death:
        """Create a death record atomically and idempotently.

        Performs the required three writes in the caller's transaction:

        1. create the death record
        2. mark the file as not alive
        3. append a DELETED event

        If the file already has a death record the existing one is returned and
        nothing new is written, guaranteeing exactly one death per file no matter
        how many DELETE events arrive.
        """
        existing = self.find_by_file_id(file.id)
        if existing is not None:
            return existing

        death = Death(
            file_id=file.id,
            filename=filename,
            original_path=original_path,
            extension=extension,
            size_bytes=size_bytes,
            born_at=born_at,
            last_modified_at=last_modified_at,
            deleted_at=deleted_at,
            lifespan_seconds=lifespan_seconds,
            cause=cause,
            epitaph=epitaph,
            cemetery_x=cemetery_x,
            cemetery_y=cemetery_y,
            created_at=utcnow(),
        )
        file.is_alive = False
        self.session.add(death)
        self.session.add(
            FileEvent(
                file_id=file.id,
                event_type=EVENT_DELETED,
                timestamp=deleted_at,
                old_path=original_path,
            )
        )
        return death


class EventRepository:
    """Persistence for :class:`~app.database.models.FileEvent` records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        file_id: int,
        event_type: str,
        timestamp: datetime,
        old_path: str | None = None,
        new_path: str | None = None,
    ) -> FileEvent:
        record = FileEvent(
            file_id=file_id,
            event_type=event_type,
            timestamp=timestamp,
            old_path=old_path,
            new_path=new_path,
        )
        self.session.add(record)
        return record

    def list_by_file(self, file_id: int, *, limit: int | None = None) -> list[FileEvent]:
        stmt = (
            select(FileEvent)
            .where(FileEvent.file_id == file_id)
            .order_by(FileEvent.timestamp.asc(), FileEvent.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list(
        self,
        *,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FileEvent]:
        stmt = select(FileEvent).order_by(FileEvent.timestamp.desc(), FileEvent.id.desc())
        if from_ is not None:
            stmt = stmt.where(FileEvent.timestamp >= from_)
        if to is not None:
            stmt = stmt.where(FileEvent.timestamp <= to)
        return list(self.session.scalars(stmt.limit(limit).offset(offset)))


class SettingRepository:
    """JSON-backed key/value settings store."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _row(self, key: str) -> Setting | None:
        return self.session.scalar(select(Setting).where(Setting.key == key))

    def get(self, key: str) -> Any | None:
        row = self._row(key)
        return json.loads(row.value) if row is not None else None

    def set(self, key: str, value: Any) -> None:
        raw = json.dumps(value)
        row = self._row(key)
        if row is None:
            self.session.add(Setting(key=key, value=raw))
        elif row.value != raw:
            row.value = raw

    def all(self) -> dict[str, Any]:
        return {
            row.key: json.loads(row.value)
            for row in self.session.scalars(select(Setting))
        }