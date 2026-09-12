"""Phase 9 tests: lifespan computation, birth derivation, and formatting."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.database.repositories import DeathRepository, FileRepository
from app.services.file_lifecycle import FileLifecycleService
from app.services.lifespan_service import (
    birth_timestamp,
    compute_lifespan,
    humanize_lifespan,
)

BASE = datetime(2026, 1, 1, 12, 0, 0)


def test_compute_lifespan_exact_seconds() -> None:
    lifespan = compute_lifespan(born_at=BASE, deleted_at=BASE + timedelta(seconds=7))
    assert lifespan.seconds == 7
    assert lifespan.born_at == BASE
    assert lifespan.deleted_at == BASE + timedelta(seconds=7)


def test_compute_lifespan_floors_partial_seconds() -> None:
    lifespan = compute_lifespan(
        born_at=BASE, deleted_at=BASE + timedelta(seconds=6, milliseconds=900)
    )
    assert lifespan.seconds == 6


def test_compute_lifespan_clamps_negative() -> None:
    lifespan = compute_lifespan(
        born_at=BASE, deleted_at=BASE - timedelta(seconds=30)
    )
    assert lifespan.seconds == 0


def test_birth_timestamp_prefers_creation_time() -> None:
    record = SimpleNamespace(
        created_at=BASE - timedelta(days=2), first_seen_at=BASE
    )
    assert birth_timestamp(record) == BASE - timedelta(days=2)


def test_birth_timestamp_falls_back_to_first_seen() -> None:
    record = SimpleNamespace(created_at=None, first_seen_at=BASE)
    assert birth_timestamp(record) == BASE


def test_humanize_lifespan_units() -> None:
    assert humanize_lifespan(0) == "0 seconds"
    assert humanize_lifespan(1) == "1 second"
    assert humanize_lifespan(59) == "59 seconds"
    assert humanize_lifespan(60) == "1 minute"
    assert humanize_lifespan(120) == "2 minutes"
    assert humanize_lifespan(3599) == "59 minutes"
    assert humanize_lifespan(3600) == "1 hour"
    assert humanize_lifespan(7200) == "2 hours"
    assert humanize_lifespan(86400) == "1 day"
    assert humanize_lifespan(172800) == "2 days"


def test_humanize_lifespan_clamps_negative() -> None:
    assert humanize_lifespan(-5) == "0 seconds"


def test_lifespan_label_property() -> None:
    lifespan = compute_lifespan(born_at=BASE, deleted_at=BASE + timedelta(seconds=180))
    assert lifespan.label == "3 minutes"


def test_lifecycle_records_lifespan_from_first_seen(database, tmp_path) -> None:
    target = tmp_path / "timed.txt"
    target.write_bytes(b"x")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))

    with database.session() as session:
        born = FileRepository(session).get_alive_by_path(str(target)).first_seen_at

    target.unlink()
    delete_time = born + timedelta(seconds=90)
    outcome = lifecycle.confirm_deletion(str(target), deleted_at=delete_time)

    assert outcome.recorded is True
    assert outcome.lifespan is not None
    assert outcome.lifespan.seconds == 90
    assert outcome.lifespan.label == "1 minute"

    with database.session() as session:
        death = DeathRepository(session).list(limit=1)[0]
        assert death.lifespan_seconds == 90
        assert death.born_at == born
        assert death.deleted_at == delete_time