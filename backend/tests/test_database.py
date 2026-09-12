"""Phase 2 tests: database initialization, models, indexes and transactions."""

from __future__ import annotations

import datetime

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError

from app.database.database import Database
from app.database.models import FileEvent, utcnow
from app.database.repositories import (
    EVENT_DELETED,
    DeathRepository,
    EventRepository,
    FileRepository,
    SettingRepository,
)


def _extension_of(path: str) -> str:
    if "." not in path.rsplit("/", 1)[-1]:
        return ""
    return "." + path.rsplit(".", 1)[-1]


def _add_file(
    database: Database,
    *,
    path: str = "/tmp/repo_x.txt",
    size: int = 100,
    filesystem_id: str = "dev:1",
) -> int:
    """Persist a live file record and return its id."""
    now = utcnow()
    with database.session() as session:
        record = FileRepository(session).create(
            path=path,
            filename=path.rsplit("/", 1)[-1],
            extension=_extension_of(path),
            size_bytes=size,
            created_at=now,
            modified_at=now,
            first_seen_at=now,
            last_seen_at=now,
            filesystem_id=filesystem_id,
        )
        session.flush()
        file_id = record.id
    return file_id


def _create_death(
    database: Database,
    file_id: int,
    *,
    deleted_at: datetime.datetime | None = None,
) -> int:
    now = deleted_at or utcnow()
    with database.session() as session:
        file = FileRepository(session).get(file_id)
        assert file is not None
        death = DeathRepository(session).create_death(
            file=file,
            filename=file.filename,
            original_path=file.path,
            extension=file.extension,
            size_bytes=file.size_bytes,
            born_at=file.first_seen_at,
            last_modified_at=file.modified_at,
            deleted_at=now,
            lifespan_seconds=0,
            cause="Unknown",
            epitaph=None,
            cemetery_x=10.0,
            cemetery_y=20.0,
        )
        session.flush()
        return death.id


def test_init_creates_all_tables(database: Database) -> None:
    inspector = sqlalchemy.inspect(database.engine)
    assert {"files", "deaths", "file_events", "settings"} == set(
        inspector.get_table_names()
    )


def test_tables_have_expected_columns(database: Database) -> None:
    inspector = sqlalchemy.inspect(database.engine)
    columns = {
        table: {col["name"] for col in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }
    assert {
        "id", "path", "filename", "extension", "size_bytes", "created_at",
        "modified_at", "first_seen_at", "last_seen_at", "filesystem_id",
        "is_alive", "created_record_at",
    }.issubset(columns["files"])

    assert {
        "id", "file_id", "filename", "original_path", "extension", "size_bytes",
        "born_at", "last_modified_at", "deleted_at", "lifespan_seconds",
        "cause", "epitaph", "cemetery_x", "cemetery_y", "created_at",
    }.issubset(columns["deaths"])

    assert {
        "id", "file_id", "event_type", "timestamp", "old_path", "new_path",
    }.issubset(columns["file_events"])

    assert {"id", "key", "value"}.issubset(columns["settings"])


def test_indexes_exist(database: Database) -> None:
    inspector = sqlalchemy.inspect(database.engine)
    index_names = {
        ix["name"]
        for table in inspector.get_table_names()
        for ix in inspector.get_indexes(table)
    }
    required = {
        "ix_files_path",
        "ix_files_filesystem_id",
        "ix_files_is_alive",
        "ix_deaths_deleted_at",
        "ix_deaths_extension",
        "ix_deaths_filename",
        "ix_file_events_file_id",
        "ix_file_events_timestamp",
    }
    assert required.issubset(index_names)


def test_file_create_read_and_query_helpers(database: Database) -> None:
    file_id = _add_file(database, path="/tmp/a.txt", filesystem_id="dev:7")

    with database.session() as session:
        repo = FileRepository(session)
        record = repo.get(file_id)
        assert record is not None
        assert record.path == "/tmp/a.txt"
        assert record.is_alive is True
        assert record.extension == ".txt"
        assert repo.get_alive_by_path("/tmp/a.txt") is not None
        assert repo.get_alive_by_path("/tmp/missing.txt") is None
        assert len(repo.list_alive()) == 1


def test_file_update_from_scan(database: Database) -> None:
    file_id = _add_file(database, size=100)
    later = utcnow()

    with database.session() as session:
        record = FileRepository(session).get(file_id)
        assert record is not None
        FileRepository(session).update_from_scan(
            record, size_bytes=500, modified_at=later, last_seen_at=later
        )

    with database.session() as session:
        record = FileRepository(session).get(file_id)
        assert record is not None
        assert record.size_bytes == 500
        assert record.last_seen_at >= record.first_seen_at


def test_foreign_keys_are_enforced(database: Database) -> None:
    now = utcnow()
    with pytest.raises(IntegrityError):
        with database.session() as session:
            session.add(FileEvent(file_id=123456, event_type="MODIFIED", timestamp=now))


def test_events_are_stored_in_chronological_order(database: Database) -> None:
    file_id = _add_file(database)
    base = utcnow()

    with database.session() as session:
        events = EventRepository(session)
        events.add(file_id=file_id, event_type="CREATED", timestamp=base)
        events.add(
            file_id=file_id,
            event_type="MODIFIED",
            timestamp=base + datetime.timedelta(seconds=5),
        )
        events.add(
            file_id=file_id,
            event_type="MOVED",
            timestamp=base + datetime.timedelta(seconds=10),
            old_path="/tmp/repo_x.txt",
            new_path="/tmp/repo_y.txt",
        )

    with database.session() as session:
        stored = EventRepository(session).list_by_file(file_id)
        assert [event.event_type for event in stored] == [
            "CREATED",
            "MODIFIED",
            "MOVED",
        ]
        assert stored[2].new_path == "/tmp/repo_y.txt"


def test_create_death_is_atomic(database: Database) -> None:
    file_id = _add_file(database, path="/tmp/gone.txt")
    deleted_at = utcnow()

    with database.session() as session:
        file = FileRepository(session).get(file_id)
        assert file is not None
        death = DeathRepository(session).create_death(
            file=file,
            filename=file.filename,
            original_path=file.path,
            extension=file.extension,
            size_bytes=file.size_bytes,
            born_at=file.first_seen_at,
            last_modified_at=file.modified_at,
            deleted_at=deleted_at,
            lifespan_seconds=0,
            cause="Unknown",
            epitaph=None,
            cemetery_x=10.0,
            cemetery_y=20.0,
        )
        session.flush()
        death_id = death.id

    with database.session() as session:
        death = DeathRepository(session).get(death_id)
        assert death is not None
        assert death.file_id == file_id
        assert death.original_path == "/tmp/gone.txt"

        file = FileRepository(session).get(file_id)
        assert file is not None
        assert file.is_alive is False

        events = EventRepository(session).list_by_file(file_id)
        assert [event.event_type for event in events] == [EVENT_DELETED]


def test_death_creation_is_idempotent(database: Database) -> None:
    file_id = _add_file(database)
    first_id = _create_death(database, file_id)
    second_id = _create_death(database, file_id)

    assert first_id == second_id

    with database.session() as session:
        assert DeathRepository(session).count() == 1
        events = EventRepository(session).list_by_file(file_id)
        assert [event.event_type for event in events] == [EVENT_DELETED]


def test_death_transaction_rolls_back_when_later_step_fails(database: Database) -> None:
    file_id = _add_file(database)

    with pytest.raises(RuntimeError):
        with database.session() as session:
            file = FileRepository(session).get(file_id)
            assert file is not None
            DeathRepository(session).create_death(
                file=file,
                filename=file.filename,
                original_path=file.path,
                extension=file.extension,
                size_bytes=file.size_bytes,
                born_at=file.first_seen_at,
                last_modified_at=file.modified_at,
                deleted_at=utcnow(),
                lifespan_seconds=0,
                cause="Unknown",
                epitaph=None,
                cemetery_x=10.0,
                cemetery_y=20.0,
            )
            session.flush()
            raise RuntimeError("simulated failure before commit")

    with database.session() as session:
        assert DeathRepository(session).count() == 0
        assert FileRepository(session).get(file_id).is_alive is True
        assert EventRepository(session).list_by_file(file_id) == []


def test_file_record_survives_after_death(database: Database) -> None:
    file_id = _add_file(database)
    _create_death(database, file_id)

    with database.session() as session:
        # The file record must remain even though the physical file is gone.
        assert FileRepository(session).get(file_id) is not None


def test_file_with_death_cannot_be_deleted(database: Database) -> None:
    file_id = _add_file(database)
    _create_death(database, file_id)

    with pytest.raises(IntegrityError):
        with database.session() as session:
            record = FileRepository(session).get(file_id)
            session.delete(record)
            session.flush()


def test_settings_roundtrip_and_defaults(database: Database) -> None:
    with database.session() as session:
        repo = SettingRepository(session)
        repo.set("watched_directories", ["/tmp/a", "/tmp/b"])
        repo.set("ignored_directories", [])
        repo.set("ai_epitaphs_enabled", False)

    with database.session() as session:
        repo = SettingRepository(session)
        assert repo.get("watched_directories") == ["/tmp/a", "/tmp/b"]
        assert repo.get("ignored_directories") == []
        assert repo.get("ai_epitaphs_enabled") is False
        assert repo.get("does_not_exist") is None
        assert repo.all()["watched_directories"] == ["/tmp/a", "/tmp/b"]


def test_empty_database_counts(database: Database) -> None:
    with database.session() as session:
        assert DeathRepository(session).count() == 0
        assert FileRepository(session).list_alive() == []
        assert EventRepository(session).list(limit=10) == []