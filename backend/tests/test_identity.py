"""Phase 4 tests: filesystem identity and record matching across renames."""

from __future__ import annotations

import os

from app.database.database import Database
from app.database.models import utcnow
from app.database.repositories import DeathRepository, FileRepository
from app.services.file_identity_service import FileIdentity, FileIdentityService


def _add_record(
    database: Database,
    *,
    path: str,
    filesystem_id: str | None,
    is_alive: bool = True,
) -> int:
    now = utcnow()
    with database.session() as session:
        record = FileRepository(session).create(
            path=path,
            filename=os.path.basename(path),
            extension=os.path.splitext(path)[1],
            size_bytes=0,
            created_at=now,
            modified_at=now,
            first_seen_at=now,
            last_seen_at=now,
            filesystem_id=filesystem_id,
        )
        record.is_alive = is_alive
        session.flush()
        return record.id


def test_identity_from_stat_returns_identity(tmp_path) -> None:
    target = tmp_path / "file.txt"
    target.write_bytes(b"x")
    identity = FileIdentityService.identity_from_stat(os.lstat(target))
    assert identity is not None
    assert identity.inode > 0
    assert identity.key == f"{identity.device}:{identity.inode}"


def test_identity_of_missing_path_is_none(tmp_path) -> None:
    service = FileIdentityService()
    assert service.identity_of(str(tmp_path / "nope.txt")) is None


def test_identity_from_stat_zero_inode_is_none() -> None:
    class _FakeStat:
        st_dev = 0
        st_ino = 0

    assert FileIdentityService.identity_from_stat(_FakeStat()) is None


def test_identity_is_stable_across_rename(tmp_path) -> None:
    service = FileIdentityService()
    original = tmp_path / "before.txt"
    renamed = tmp_path / "after.txt"
    original.write_bytes(b"payload")

    before = service.identity_of(str(original))
    os.rename(original, renamed)
    after = service.identity_of(str(renamed))

    assert before is not None
    assert before == after


def test_match_keeps_same_record_across_rename(
    database: Database, tmp_path
) -> None:
    """The core goal: a renamed physical file maps to the SAME record."""
    service = FileIdentityService()
    original = tmp_path / "draft.txt"
    renamed = tmp_path / "final.txt"
    original.write_bytes(b"content")

    identity = service.identity_of(str(original))
    assert identity is not None
    record_id = _add_record(
        database, path=str(original), filesystem_id=identity.key
    )

    os.rename(original, renamed)

    with database.session() as session:
        matched = service.match_existing_file(FileRepository(session), str(renamed))
        assert matched is not None
        assert matched.id == record_id
        # The record still points at the old path until the processor updates it.
        assert matched.path == str(original)


def test_match_falls_back_to_path_when_identity_unavailable(
    database: Database, tmp_path, monkeypatch
) -> None:
    service = FileIdentityService()
    target = tmp_path / "fallback.txt"
    target.write_bytes(b"y")
    record_id = _add_record(database, path=str(target), filesystem_id=None)

    monkeypatch.setattr(service, "identity_of", lambda path: None)

    with database.session() as session:
        matched = service.match_existing_file(FileRepository(session), str(target))
        assert matched is not None
        assert matched.id == record_id


def test_match_returns_none_for_unknown_file(
    database: Database, tmp_path
) -> None:
    service = FileIdentityService()
    target = tmp_path / "unknown.txt"
    target.write_bytes(b"z")

    with database.session() as session:
        assert service.match_existing_file(FileRepository(session), str(target)) is None


def test_distinct_files_have_distinct_identity(tmp_path) -> None:
    service = FileIdentityService()
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    assert service.identity_of(str(a)) != service.identity_of(str(b))


def test_match_ignores_dead_records(database: Database, tmp_path) -> None:
    service = FileIdentityService()
    target = tmp_path / "dead.txt"
    target.write_bytes(b"d")
    identity = service.identity_of(str(target))
    assert identity is not None
    record_id = _add_record(database, path=str(target), filesystem_id=identity.key)

    with database.session() as session:
        record = FileRepository(session).get(record_id)
        DeathRepository(session).create_death(
            file=record,
            filename=record.filename,
            original_path=record.path,
            extension=record.extension,
            size_bytes=record.size_bytes,
            born_at=record.first_seen_at,
            last_modified_at=record.modified_at,
            deleted_at=utcnow(),
            lifespan_seconds=0,
            cause="Unknown",
            epitaph=None,
            cemetery_x=0.0,
            cemetery_y=0.0,
        )

    with database.session() as session:
        # A dead record must not be matched again, even if the inode is reused.
        assert service.match_existing_file(FileRepository(session), str(target)) is None


def test_new_file_at_old_path_is_not_the_dead_record(
    database: Database, tmp_path
) -> None:
    service = FileIdentityService()
    path = tmp_path / "reused.txt"
    path.write_bytes(b"old")

    old_identity = service.identity_of(str(path))
    assert old_identity is not None
    old_id = _add_record(database, path=str(path), filesystem_id=old_identity.key)

    with database.session() as session:
        record = FileRepository(session).get(old_id)
        DeathRepository(session).create_death(
            file=record,
            filename=record.filename,
            original_path=record.path,
            extension=record.extension,
            size_bytes=record.size_bytes,
            born_at=record.first_seen_at,
            last_modified_at=record.modified_at,
            deleted_at=utcnow(),
            lifespan_seconds=0,
            cause="Unknown",
            epitaph=None,
            cemetery_x=0.0,
            cemetery_y=0.0,
        )

    path.unlink()
    path.write_bytes(b"new file")

    with database.session() as session:
        # The path now hosts a different physical file with no record yet.
        assert service.match_existing_file(FileRepository(session), str(path)) is None


def test_file_identity_key_format() -> None:
    assert FileIdentity(device=2049, inode=42).key == "2049:42"