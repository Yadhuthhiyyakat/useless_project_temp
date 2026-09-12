"""Phase 8 tests: file lifecycle state machine and death confirmation."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from app.database.repositories import (
    EVENT_CREATED,
    EVENT_DELETED,
    DeathRepository,
    EventRepository,
    FileRepository,
)
from app.services.file_lifecycle import FileLifecycleService
from app.watcher.events import EventKind, FileSystemEvent
from app.watcher.processor import EventProcessor


def _service(database):
    return FileLifecycleService(database)


def _alive_by_path(database, path):
    with database.session() as session:
        return FileRepository(session).get_alive_by_path(str(path))


def _death_count(database) -> int:
    with database.session() as session:
        return DeathRepository(session).count()


def _record(database, file_id):
    with database.session() as session:
        return FileRepository(session).get(file_id)


def _event_types_for(database, file_id) -> list[str]:
    with database.session() as session:
        return [e.event_type for e in EventRepository(session).list_by_file(file_id)]


def test_false_deletion_is_cancelled(database, tmp_path) -> None:
    target = tmp_path / "alive.txt"
    target.write_bytes(b"still here")
    lifecycle = _service(database)
    lifecycle.register(str(target))

    outcome = lifecycle.confirm_deletion(str(target))

    assert outcome.recorded is False
    assert outcome.reason == "file_still_present"
    assert _death_count(database) == 0
    record = _alive_by_path(database, target)
    assert record is not None and record.is_alive is True


def test_confirmed_deletion_records_immortal_death(database, tmp_path) -> None:
    target = tmp_path / "doomed.txt"
    target.write_bytes(b"x")
    lifecycle = _service(database)
    lifecycle.register(str(target))

    target.unlink()
    outcome = lifecycle.confirm_deletion(str(target))

    assert outcome.recorded is True
    assert outcome.reason == "death_recorded"
    assert _death_count(database) == 1
    assert _alive_by_path(database, target) is None

    second = lifecycle.confirm_deletion(str(target))
    assert second.recorded is False
    assert second.reason == "unknown_file"
    assert _death_count(database) == 1  # still exactly one death


def test_dead_record_is_never_resurrected(database, tmp_path) -> None:
    target = tmp_path / "phoenix.txt"
    target.write_bytes(b"first life")
    lifecycle = _service(database)
    lifecycle.register(str(target))

    with database.session() as session:
        old_id = FileRepository(session).get_alive_by_path(str(target)).id

    target.unlink()
    first_death = lifecycle.confirm_deletion(str(target))
    assert first_death.recorded is True

    target.write_bytes(b"second life, same path")
    result = lifecycle.register(str(target))

    with database.session() as session:
        alive_records = [r for r in FileRepository(session).list_alive()]
        assert len(alive_records) == 1
        new_id = alive_records[0].id
        old_record = FileRepository(session).get(old_id)
        assert old_record.is_alive is False
        assert old_record.path == str(target)
    assert new_id != old_id
    assert result.created is True
    assert _death_count(database) == 1

    assert _event_types_for(database, old_id) == [EVENT_CREATED, EVENT_DELETED]
    assert _event_types_for(database, new_id) == [EVENT_CREATED]


def test_dead_path_cannot_accept_updates(database, tmp_path) -> None:
    target = tmp_path / "tomb.txt"
    target.write_bytes(b"one")
    processor = EventProcessor(database, watched_directories=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))
    with database.session() as session:
        dead_id = FileRepository(session).get_alive_by_path(str(target)).id

    target.unlink()
    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))

    target.write_bytes(b"two whoa much longer content")
    processor.process(FileSystemEvent(kind=EventKind.MODIFIED, src_path=str(target)))

    old_record = _record(database, dead_id)
    assert old_record.is_alive is False
    assert old_record.size_bytes == len(b"one")
    with database.session() as session:
        new_record = FileRepository(session).get_alive_by_path(str(target))
    assert new_record is not None
    assert new_record.id != dead_id
    assert new_record.size_bytes == len(b"two whoa much longer content")


def test_directory_replacing_file_counts_as_death(database, tmp_path) -> None:
    target = tmp_path / "turned_dir.txt"
    target.write_bytes(b"x")
    lifecycle = _service(database)
    lifecycle.register(str(target))

    target.unlink()
    target.mkdir()
    outcome = lifecycle.confirm_deletion(str(target))

    assert outcome.recorded is True
    assert _death_count(database) == 1
    assert _alive_by_path(database, target) is None


def test_processor_routes_false_delete_to_lifecycle(database, tmp_path) -> None:
    target = tmp_path / "briefly_missing.txt"
    target.write_bytes(b"x")
    processor = EventProcessor(database, watched_directories=[str(tmp_path)])
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))

    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))

    assert _death_count(database) == 0
    assert _alive_by_path(database, target) is not None


def test_move_after_death_starts_new_record_not_resurrection(database, tmp_path) -> None:
    target = tmp_path / "old.txt"
    target.write_bytes(b"data")
    lifecycle = _service(database)
    lifecycle.register(str(target))
    with database.session() as session:
        old_id = FileRepository(session).get_alive_by_path(str(target)).id

    target.unlink()
    lifecycle.confirm_deletion(str(target))
    assert _death_count(database) == 1

    target.write_bytes(b"reborn")
    moved_to = tmp_path / "new.txt"
    os.rename(target, moved_to)
    lifecycle.register(str(moved_to))

    with database.session() as session:
        alive_records = [r for r in FileRepository(session).list_alive()]
        assert len(alive_records) == 1
        assert alive_records[0].id != old_id
        assert alive_records[0].path == str(moved_to)
        assert _record(database, old_id).is_alive is False
    assert _death_count(database) == 1


def test_delete_event_timestamp_becomes_death_time(database, tmp_path) -> None:
    target = tmp_path / "timestamped.txt"
    target.write_bytes(b"x")
    lifecycle = _service(database)
    lifecycle.register(str(target))
    with database.session() as session:
        born = FileRepository(session).get_alive_by_path(str(target)).first_seen_at

    target.unlink()
    delete_time = born + timedelta(seconds=5)
    outcome = lifecycle.confirm_deletion(str(target), deleted_at=delete_time)

    assert outcome.recorded is True
    with database.session() as session:
        death = DeathRepository(session).list(limit=1)[0]
        assert death.deleted_at == delete_time
        assert death.lifespan_seconds == 5