"""Phase 5 tests: initial directory scan and re-scan idempotency."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from app.database.database import Database
from app.database.repositories import EventRepository, FileRepository
from app.services.scan_service import ScanService


def _create_service(database: Database) -> ScanService:
    return ScanService(database)


def _alive_count(database: Database) -> int:
    with database.session() as session:
        return len(FileRepository(session).list_alive())


def _event_types(database: Database) -> list[tuple[int, str]]:
    with database.session() as session:
        return [
            (event.file_id, event.event_type)
            for event in EventRepository(session).list(limit=1000)
        ]


def _mkdir_in(root, rel: str):
    target = root / rel
    target.mkdir(parents=True, exist_ok=True)
    return target


def test_scan_empty_directory(database: Database, tmp_path) -> None:
    service = _create_service(database)
    result = service.scan_directory(str(tmp_path))
    assert result.files_found == 0
    assert result.files_created == 0
    assert result.errors == []
    assert _alive_count(database) == 0


def test_scan_discovers_files_and_creates_records(
    database: Database, tmp_path
) -> None:
    (tmp_path / "one.txt").write_bytes(b"a")
    (tmp_path / "two.pdf").write_bytes(b"b" * 20)
    nested = _mkdir_in(tmp_path, "nested")
    (nested / "three.py").write_bytes(b"c")

    result = _create_service(database).scan_directory(str(tmp_path))

    assert result.files_found == 3
    assert result.files_created == 3
    assert result.errors == []
    assert _alive_count(database) == 3

    events = _event_types(database)
    created_events = [(fid, etype) for fid, etype in events if etype == "CREATED"]
    assert len(created_events) == 3
    assert len(events) == 3


def test_scan_is_idempotent(database: Database, tmp_path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    (tmp_path / "b.txt").write_bytes(b"b")

    service = _create_service(database)
    first = service.scan_directory(str(tmp_path))
    second = service.scan_directory(str(tmp_path))
    third = service.scan_directory(str(tmp_path))

    assert first.files_created == 2
    assert second.files_created == 0
    assert third.files_created == 0
    assert second.files_updated == 2
    assert third.files_updated == 2
    assert second.events_added == 0
    assert third.events_added == 0
    assert _alive_count(database) == 2
    assert len([e for e in _event_types(database) if e[1] == "CREATED"]) == 2


def test_scan_detects_new_files_added_later(database: Database, tmp_path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    service = _create_service(database)
    service.scan_directory(str(tmp_path))

    (tmp_path / "b.txt").write_bytes(b"b")
    result = service.scan_directory(str(tmp_path))

    assert result.files_created == 1
    assert _alive_count(database) == 2


def test_scan_detects_modification_as_single_event(database: Database, tmp_path) -> None:
    target = tmp_path / "edit.txt"
    target.write_bytes(b"short")
    service = _create_service(database)
    service.scan_directory(str(tmp_path))

    target.write_bytes(b"a much longer payload than before")
    result = service.scan_directory(str(tmp_path))

    assert result.files_updated == 1
    modified = [e for e in _event_types(database) if e[1] == "MODIFIED"]
    assert len(modified) == 1

    with database.session() as session:
        record = FileRepository(session).get_alive_by_path(str(target))
        assert record is not None
        assert record.size_bytes == len(b"a much longer payload than before")


def test_scan_keeps_same_record_across_rename(
    database: Database, tmp_path
) -> None:
    before = tmp_path / "before.txt"
    after = tmp_path / "after.txt"
    before.write_bytes(b"payload")
    service = _create_service(database)
    first = service.scan_directory(str(tmp_path))
    assert first.files_created == 1

    with database.session() as session:
        original_id = FileRepository(session).get_alive_by_path(str(before)).id

    os.rename(before, after)
    second = service.scan_directory(str(tmp_path))

    assert second.files_created == 0
    assert _alive_count(database) == 1
    moved = [e for e in _event_types(database) if e[1] == "MOVED"]
    assert len(moved) == 1
    assert moved[0][0] == original_id  # same record id as the original

    with database.session() as session:
        record = FileRepository(session).get(moved[0][0])
        assert record is not None
        assert record.path == str(after)
        assert record.filename == "after.txt"


def test_scan_respects_ignored_directories(database: Database, tmp_path) -> None:
    (tmp_path / "keep.txt").write_bytes(b"keep")
    skip = _mkdir_in(tmp_path, "skip")
    (skip / "x.txt").write_bytes(b"x")
    deeper = _mkdir_in(tmp_path, "skip/deeper")
    (deeper / "y.txt").write_bytes(b"y")

    result = _create_service(database).scan_directory(
        str(tmp_path), ignored_directories=[str(skip)]
    )

    assert result.files_found == 1
    assert _alive_count(database) == 1
    with database.session() as session:
        assert FileRepository(session).get_alive_by_path(str(tmp_path / "keep.txt"))


def test_scan_does_not_follow_symlinked_directories(
    database: Database, tmp_path
) -> None:
    outside = tempfile.mkdtemp(dir=tmp_path.parent)
    try:
        with open(os.path.join(outside, "hidden.txt"), "w") as handle:
            handle.write("h")
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)

        result = _create_service(database).scan_directory(str(tmp_path))
        assert result.files_found == 0
        assert _alive_count(database) == 0
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def test_scan_missing_directory_reports_error(database: Database, tmp_path) -> None:
    missing = tmp_path / "missing_dir"
    result = _create_service(database).scan_directory(str(missing))
    assert result.errors
    assert result.files_found == 0


def test_scan_file_path_reports_error(database: Database, tmp_path) -> None:
    target = tmp_path / "i_am_a_file.txt"
    target.write_bytes(b"x")
    result = _create_service(database).scan_directory(str(target))
    assert result.errors
    assert result.files_found == 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_scan_reports_inaccessible_subdirectory(
    database: Database, tmp_path
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "secret.txt").write_bytes(b"s")
    (tmp_path / "ok.txt").write_bytes(b"o")
    locked.chmod(0o000)
    try:
        result = _create_service(database).scan_directory(str(tmp_path))
        assert result.files_found == 1
        assert result.errors
        assert _alive_count(database) == 1
    finally:
        locked.chmod(0o700)


def test_scan_last_seen_and_alive_state(database: Database, tmp_path) -> None:
    target = tmp_path / "state.txt"
    target.write_bytes(b"s")
    _create_service(database).scan_directory(str(tmp_path))

    with database.session() as session:
        record = FileRepository(session).get_alive_by_path(str(target))
        assert record is not None
        assert record.is_alive is True
        assert record.first_seen_at is not None
        assert record.last_seen_at is not None