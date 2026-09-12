"""SQLAlchemy ORM models for the Digital Cemetery backend.

All timestamps are stored as naive UTC datetimes. File records are never
physically deleted: a record must remain after the underlying file is gone so
that death records stay permanent historical data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime for SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


class File(Base):
    """A file as observed by the backend.

    The record outlives the physical file. ``is_alive`` tracks whether the file
    still exists on disk. ``filesystem_id`` is a stable identity (e.g.
    ``device:inode``) used to keep the same record across rename/move.
    """

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    extension: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filesystem_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_record_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    deaths: Mapped[list["Death"]] = relationship(
        back_populates="file", passive_deletes=True
    )
    events: Mapped[list["FileEvent"]] = relationship(
        back_populates="file",
        passive_deletes=True,
        order_by="FileEvent.timestamp",
    )

    __table_args__ = (
        Index("ix_files_path", "path"),
        Index("ix_files_filesystem_id", "filesystem_id"),
        Index("ix_files_is_alive", "is_alive"),
        Index("ix_files_extension", "extension"),
        Index("ix_files_filename", "filename"),
        Index("ix_files_last_seen_at", "last_seen_at"),
    )


class Death(Base):
    """A permanent digital death record for a deleted file.

    This record is immutable by design and is never deleted.
    """

    __tablename__ = "deaths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_path: Mapped[str] = mapped_column(String(4096), nullable=False)
    extension: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    born_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lifespan_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cause: Mapped[str] = mapped_column(String(128), nullable=False, default="Unknown")
    epitaph: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cemetery_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cemetery_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    file: Mapped[File] = relationship(back_populates="deaths")

    __table_args__ = (
        Index("ix_deaths_file_id", "file_id"),
        Index("ix_deaths_deleted_at", "deleted_at"),
        Index("ix_deaths_extension", "extension"),
        Index("ix_deaths_filename", "filename"),
        Index("ix_deaths_cause", "cause"),
    )


class FileEvent(Base):
    """A single lifecycle event (CREATED / MODIFIED / MOVED / DELETED).

    Kept for an entire file's life so its history can be reconstructed.
    """

    __tablename__ = "file_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    old_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    new_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    file: Mapped[File] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_file_events_file_id", "file_id"),
        Index("ix_file_events_timestamp", "timestamp"),
        Index("ix_file_events_event_type", "event_type"),
    )


class Setting(Base):
    """An extensible key/value settings store.

    Values are JSON-encoded strings so new settings can be added without schema
    changes. This table sources the persisted settings API (watched directories,
    ignored directories, AI epitaph toggle) exposed in a later phase.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(4096), nullable=False)

    __table_args__ = (
        Index("ix_settings_key", "key", unique=True),
        UniqueConstraint("key", name="uq_settings_key"),
    )