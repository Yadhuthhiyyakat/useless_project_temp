"""Phase 7 tests: the event processor turns watcher events into database state."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database.repositories import (
    EVENT_CREATED,
    EVENT_DELETED,
    EVENT_MODIFIED,
    EVENT_MOVED,
    DeathRepository,
    EventRepository,
    FileRepository,
)
from app.watcher.events import EventKind, FileSystemEvent
from app.watcher.filesystem import FileEventHandler, WatcherService
from app.watcher.processor import CAUSE_DELETE_DETECTED, EventProcessor


def _utc_naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _processor(database, ignored=(), watched=()):
    return EventProcessor(database, ignored_directories=ignored, watched_directories=watched)


def _alive_by_path(database, path) -> object | None:
    with database.session() as session:
        return FileRepository(session).get_alive_by_path(str(path))


def _event_types(database) -> list[str]:
    with database.session() as session:
        events = EventRepository(session).list(limit=1000)
    return [e.event_type for e in reversed(events)]


def _death_count(database) -> int:
    with database.session() as session:
        return DeathRepository(session).count()


def _recent_death(database):
    with database.session() as session:
        return DeathRepository(session).list(limit=1)[0]


def test_created_event_registers_new_file(database, tmp_path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"x")
    _processor(database, watched=[str(tmp_path)]).process(
        FileSystemEvent(kind=EventKind.CREATED, src_path=str(target))
    )

    record = _alive_by_path(database, target)
    assert record is not None
    assert record.filename == "a.txt"
    assert record.is_alive is True
    assert _event_types(database) == [EVENT_CREATED]


def test_created_event_is_idempotent(database, tmp_path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"x")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))

    assert _alive_by_path(database, target) is not None
    assert _event_types(database) == [EVENT_CREATED]


def test_modified_event_updates_size_and_records_event(database, tmp_path) -> None:
    target = tmp_path / "edit.txt"
    target.write_bytes(b"short")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))

    target.write_bytes(b"a much longer payload than before")
    processor.process(FileSystemEvent(kind=EventKind.MODIFIED, src_path=str(target)))

    recorded = _alive_by_path(database, target)
    assert recorded.size_bytes == len(b"a much longer payload than before")
    assert _event_types(database) == [EVENT_CREATED, EVENT_MODIFIED]


def test_modified_event_registers_unknown_file(database, tmp_path) -> None:
    target = tmp_path / "late.txt"
    target.write_bytes(b"z")
    _processor(database, watched=[str(tmp_path)]).process(
        FileSystemEvent(kind=EventKind.MODIFIED, src_path=str(target))
    )
    assert _alive_by_path(database, target) is not None
    assert _event_types(database) == [EVENT_CREATED]


def test_moved_event_rehomes_same_record(database, tmp_path) -> None:
    before = tmp_path / "before.txt"
    after = tmp_path / "after.txt"
    before.write_bytes(b"payload")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(before)))

    with database.session() as session:
        original_id = FileRepository(session).get_alive_by_path(str(before)).id

    os.rename(before, after)
    processor.process(
        FileSystemEvent(kind=EventKind.MOVED, src_path=str(before), dest_path=str(after))
    )

    recorded = _alive_by_path(database, after)
    assert recorded is not None
    assert recorded.id == original_id
    assert recorded.path == str(after)
    assert recorded.filename == "after.txt"
    assert _event_types(database) == [EVENT_CREATED, EVENT_MOVED]


def test_ignored_directories_are_skipped(database, tmp_path) -> None:
    skipped = tmp_path / "ignored"
    skipped.mkdir()
    target = skipped / "x.txt"
    target.write_bytes(b"x")
    processor = _processor(database, ignored=[str(skipped)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))
    assert _alive_by_path(database, target) is None


def test_database_sidecars_are_ignored(database, tmp_path) -> None:
    db_path = (tmp_path / "test.db").resolve()
    assert db_path.exists()
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(
        FileSystemEvent(kind=EventKind.CREATED, src_path=str(db_path))
    )
    for suffix in ("-wal", "-shm", "-journal"):
        processor.process(
            FileSystemEvent(
                kind=EventKind.CREATED, src_path=str(tmp_path / f"test.db{suffix}")
            )
        )
    for candidate in [
        str(db_path),
        str(db_path) + "-wal",
    ]:
        assert _alive_by_path(database, candidate) is None


def test_deleted_event_creates_death_record(database, tmp_path) -> None:
    target = tmp_path / "doomed.txt"
    target.write_bytes(b"secrets")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))

    target.unlink()
    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))

    assert _death_count(database) == 1
    record = _alive_by_path(database, target)
    assert record is None
    death = _recent_death(database)
    assert death.original_path == str(target)
    assert death.filename == "doomed.txt"
    assert death.extension == ".txt"
    assert death.cause == CAUSE_DELETE_DETECTED
    assert EVENT_DELETED in _event_types(database)


def test_deleted_event_records_lifespan(database, tmp_path) -> None:
    target = tmp_path / "aged.txt"
    target.write_bytes(b"x")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))

    with database.session() as session:
        born = FileRepository(session).get_alive_by_path(str(target)).first_seen_at
    target.unlink()
    delete_time = born + timedelta(seconds=7)
    processor.process(
        FileSystemEvent(
            kind=EventKind.DELETED, src_path=str(target), timestamp=delete_time
        )
    )

    assert _recent_death(database).lifespan_seconds == 7


def test_deleted_event_for_unknown_file_is_noop(database, tmp_path) -> None:
    _processor(database, watched=[str(tmp_path)]).process(
        FileSystemEvent(kind=EventKind.DELETED, src_path=str(tmp_path / "ghost.txt"))
    )
    assert _death_count(database) == 0


def test_deleted_event_is_idempotent(database, tmp_path) -> None:
    target = tmp_path / "once.txt"
    target.write_bytes(b"x")
    processor = _processor(database, watched=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))
    target.unlink()
    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))
    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))

    assert _death_count(database) == 1
    assert [e for e in _event_types(database) if e == EVENT_DELETED].count(EVENT_DELETED) == 1


def test_full_watcher_loop_creates_and_mourns(database, tmp_path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    processor = _processor(database, watched=[str(watched)])
    service = WatcherService(FileEventHandler(processor))
    service.add_directory(str(watched))
    service.start()
    try:
        target = watched / "born_and_dead.txt"
        target.write_bytes(b"hello")
        assert _wait_for(lambda: _alive_by_path(database, target) is not None)

        target.unlink()
        assert _wait_for(lambda: _death_count(database) == 1)

        record = _recent_death(database)
        assert record.filename == "born_and_dead.txt"
        assert record.original_path == str(target)
    finally:
        service.stop()
        assert service.running is False


def _wait_for(condition, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False