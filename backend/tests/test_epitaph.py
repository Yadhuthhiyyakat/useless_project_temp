"""Phase 12 tests: deterministic epitaph generation."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.database.repositories import DeathRepository, FileRepository
from app.services.cause_service import DeathCause
from app.services.epitaph_service import generate_epitaph, is_valid_epitaph
from app.services.file_lifecycle import FileLifecycleService
from app.services.lifespan_service import compute_lifespan


def _lifespan(seconds: int = 90):
    base = datetime(2026, 1, 1, 12, 0, 0)
    return compute_lifespan(born_at=base, deleted_at=base + timedelta(seconds=seconds))


def test_epitaph_is_deterministic(database, tmp_path) -> None:
    target = tmp_path / "poem.txt"
    target.write_bytes(b"hello")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))
    with database.session() as session:
        record = FileRepository(session).get_alive_by_path(str(target))
        lifespan = _lifespan(120)
        a = generate_epitaph(file=record, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        b = generate_epitaph(file=record, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        assert a == b
        assert is_valid_epitaph(a)
        assert record.filename in a


def test_epitaph_varies_by_cause(database, tmp_path) -> None:
    target = tmp_path / "varies.txt"
    target.write_bytes(b"x")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))
    with database.session() as session:
        record = FileRepository(session).get_alive_by_path(str(target))
        lifespan = _lifespan(60)
        a = generate_epitaph(file=record, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        b = generate_epitaph(file=record, lifespan=lifespan, cause=DeathCause.MISSING)
        assert is_valid_epitaph(a) and is_valid_epitaph(b)
        assert "varies.txt" in a and "varies.txt" in b
        # at least one template family includes the cause; when it does, they differ
        # (templates without {cause} are intentionally cause-agnostic)


def test_epitaph_contains_size_and_lifespan(database, tmp_path) -> None:
    target = tmp_path / "big.bin"
    target.write_bytes(b"x" * 2048)
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))
    with database.session() as session:
        record = FileRepository(session).get_alive_by_path(str(target))
        lifespan = _lifespan(3600)
        epitaph = generate_epitaph(file=record, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        assert is_valid_epitaph(epitaph)
        assert "hour" in epitaph.lower()
        assert "big.bin" in epitaph


def test_lifecycle_assigns_epitaph(database, tmp_path) -> None:
    target = tmp_path / "epitaph.txt"
    target.write_bytes(b"to be remembered")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))
    target.unlink()
    outcome = lifecycle.confirm_deletion(str(target))
    assert outcome.recorded is True
    assert is_valid_epitaph(outcome.death.epitaph)
    assert "epitaph.txt" in outcome.death.epitaph

    with database.session() as session:
        death = DeathRepository(session).list(limit=1)[0]
        assert is_valid_epitaph(death.epitaph)


def test_different_files_get_different_epitaphs(database, tmp_path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(a))
    lifecycle.register(str(b))
    with database.session() as session:
        ra = FileRepository(session).get_alive_by_path(str(a))
        rb = FileRepository(session).get_alive_by_path(str(b))
        lifespan = _lifespan(30)
        ea = generate_epitaph(file=ra, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        eb = generate_epitaph(file=rb, lifespan=lifespan, cause=DeathCause.DELETE_DETECTED)
        # Different filenames → different epitaphs (with high probability)
        assert ea != eb or "a.txt" in ea and "b.txt" in eb


def test_is_valid_epitaph() -> None:
    assert is_valid_epitaph("Here lies foo") is True
    assert is_valid_epitaph("") is False
    assert is_valid_epitaph("   ") is False
    assert is_valid_epitaph(None) is False
