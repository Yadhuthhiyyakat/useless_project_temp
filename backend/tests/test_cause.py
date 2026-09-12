"""Phase 10 tests: death cause taxonomy."""

from __future__ import annotations

from app.database.repositories import DeathRepository, FileRepository
from app.services.cause_service import DeathCause, determine_cause, is_valid_cause
from app.services.file_lifecycle import DEATH_CAUSE_DELETE_DETECTED, FileLifecycleService
from app.watcher.events import EventKind
from app.watcher.processor import EventProcessor, CAUSE_DELETE_DETECTED


def test_death_cause_enum_values() -> None:
    assert DeathCause.DELETE_DETECTED.value == "DELETE_DETECTED"
    assert DeathCause.UNKNOWN.value == "Unknown"
    assert DeathCause.MISSING.value == "MISSING"
    # Str-enum equality: members compare equal to their raw string values.
    assert DeathCause.DELETE_DETECTED == "DELETE_DETECTED"
    assert DeathCause.UNKNOWN == "Unknown"


def test_death_cause_labels() -> None:
    assert DeathCause.DELETE_DETECTED.label == "Deleted"
    assert DeathCause.UNKNOWN.label == "Unknown"
    assert DeathCause.MISSING.label == "Missing"


def test_is_valid_cause() -> None:
    assert is_valid_cause("DELETE_DETECTED") is True
    assert is_valid_cause("Unknown") is True
    assert is_valid_cause("MISSING") is True
    assert is_valid_cause("banana") is False
    assert is_valid_cause("") is False


def test_determine_cause_for_deleted_event() -> None:
    assert determine_cause(event_kind=EventKind.DELETED) is DeathCause.DELETE_DETECTED
    assert determine_cause(event_kind="DELETED") is DeathCause.DELETE_DETECTED


def test_determine_cause_for_missing_without_event() -> None:
    assert determine_cause(event_kind=None) is DeathCause.MISSING


def test_determine_cause_falls_back_to_unknown() -> None:
    assert determine_cause(event_kind=EventKind.CREATED) is DeathCause.UNKNOWN
    assert determine_cause(event_kind="SOMETHING_ELSE") is DeathCause.UNKNOWN


def test_backwards_compatible_constant() -> None:
    assert DEATH_CAUSE_DELETE_DETECTED == "DELETE_DETECTED"
    assert CAUSE_DELETE_DETECTED == "DELETE_DETECTED"
    assert DEATH_CAUSE_DELETE_DETECTED == DeathCause.DELETE_DETECTED.value


def test_lifecycle_records_taxonomy_cause(database, tmp_path) -> None:
    target = tmp_path / "victim.txt"
    target.write_bytes(b"x")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))

    target.unlink()
    outcome = lifecycle.confirm_deletion(str(target))

    assert outcome.recorded is True
    assert outcome.death is not None
    assert outcome.death.cause == DeathCause.DELETE_DETECTED.value
    assert is_valid_cause(outcome.death.cause)

    with database.session() as session:
        death = DeathRepository(session).list(limit=1)[0]
        assert death.cause == "DELETE_DETECTED"


def test_processor_still_records_delete_detected(database, tmp_path) -> None:
    target = tmp_path / "via_processor.txt"
    target.write_bytes(b"x")
    processor = EventProcessor(database, watched_directories=[str(tmp_path)])
    from app.watcher.events import FileSystemEvent

    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(target)))
    target.unlink()
    processor.process(FileSystemEvent(kind=EventKind.DELETED, src_path=str(target)))

    with database.session() as session:
        death = DeathRepository(session).list(limit=1)[0]
        assert death.cause == DeathCause.DELETE_DETECTED
        assert death.cause == "DELETE_DETECTED"
