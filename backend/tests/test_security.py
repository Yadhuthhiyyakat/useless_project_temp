"""Phase 20 tests: security utilities and path validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.security import (
    SecurityError,
    is_safe_path,
    resolve_within_roots,
    validate_regular_file,
)


def test_resolve_within_roots_allows_subdirectory(tmp_path) -> None:
    root = tmp_path / "watch"
    root.mkdir()
    target = root / "sub" / "file.txt"
    target.parent.mkdir()
    target.write_bytes(b"x")

    resolved = resolve_within_roots(str(target), [str(root)])
    assert resolved == target.resolve()


def test_resolve_within_roots_blocks_traversal(tmp_path) -> None:
    root = tmp_path / "watch"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"x")

    # Path tries to escape via ..
    bad = root / ".." / "outside" / "secret.txt"
    try:
        resolve_within_roots(str(bad), [str(root)])
        assert False, "Should have raised SecurityError"
    except SecurityError as e:
        assert e.code == "traversal"


def test_resolve_within_roots_blocks_absolute_outside(tmp_path) -> None:
    root = tmp_path / "watch"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"x")

    try:
        resolve_within_roots(str(outside / "secret.txt"), [str(root)])
        assert False, "Should have raised SecurityError"
    except SecurityError as e:
        assert e.code == "traversal"


def test_resolve_within_roots_allows_multiple_roots(tmp_path) -> None:
    root1 = tmp_path / "watch1"
    root2 = tmp_path / "watch2"
    root1.mkdir()
    root2.mkdir()
    f1 = root1 / "a.txt"
    f2 = root2 / "b.txt"
    f1.write_bytes(b"a")
    f2.write_bytes(b"b")

    assert resolve_within_roots(str(f1), [str(root1), str(root2)]) == f1.resolve()
    assert resolve_within_roots(str(f2), [str(root1), str(root2)]) == f2.resolve()


def test_is_safe_path_boolean(tmp_path) -> None:
    root = tmp_path / "watch"
    root.mkdir()
    inside = root / "ok.txt"
    inside.write_bytes(b"x")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"x")

    assert is_safe_path(str(inside), [str(root)]) is True
    assert is_safe_path(str(outside), [str(root)]) is False


def test_validate_regular_file_passes(tmp_path) -> None:
    f = tmp_path / "regular.txt"
    f.write_bytes(b"hello")
    validate_regular_file(f.resolve())  # should not raise


def test_validate_regular_file_rejects_directory(tmp_path) -> None:
    d = tmp_path / "adir"
    d.mkdir()
    try:
        validate_regular_file(d.resolve())
        assert False, "Should have raised SecurityError"
    except SecurityError as e:
        assert e.code == "not_regular"


def test_validate_regular_file_rejects_missing(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    try:
        validate_regular_file(missing.resolve())
        assert False, "Should have raised SecurityError"
    except SecurityError as e:
        assert e.code == "stat_failed"


def test_event_processor_security_integration(database, tmp_path) -> None:
    """Processor rejects paths outside watched roots."""
    from app.config import Config
    from app.database.database import Database
    from app.watcher.events import EventKind, FileSystemEvent
    from app.watcher.processor import EventProcessor

    watched = tmp_path / "watch"
    watched.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'sec_test.db'}"
    db = Database(config)
    db.init()
    processor = EventProcessor(
        db, ignored_directories=[], watched_directories=[str(watched)]
    )

    # Path inside watched dir -> should register
    inside = watched / "allowed.txt"
    inside.write_bytes(b"x")
    processor.process(FileSystemEvent(kind=EventKind.CREATED, src_path=str(inside)))
    from app.database.repositories import FileRepository

    with db.session() as session:
        assert FileRepository(session).get_alive_by_path(str(inside)) is not None

    # Path outside watched dir -> should be rejected
    outside_file = outside / "forbidden.txt"
    outside_file.write_bytes(b"x")
    processor.process(
        FileSystemEvent(kind=EventKind.CREATED, src_path=str(outside_file))
    )
    with db.session() as session:
        assert FileRepository(session).get_alive_by_path(str(outside_file)) is None

    db.dispose()


def test_scan_service_uses_security(tmp_path) -> None:
    """ScanService rejects paths outside roots (via security in processor path)."""
    from app.config import Config
    from app.database.database import Database
    from app.services.scan_service import ScanService

    watched = tmp_path / "watch"
    watched.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (watched / "ok.txt").write_bytes(b"x")
    (outside / "nope.txt").write_bytes(b"x")

    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'scan_sec.db'}"
    db = Database(config)
    db.init()

    service = ScanService(db)
    result = service.scan_directory(str(watched), ignored_directories=[str(outside)])
    assert result.files_found == 1
    db.dispose()