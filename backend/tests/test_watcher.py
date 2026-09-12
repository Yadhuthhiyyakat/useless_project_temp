"""Phase 6 tests: event normalization and the filesystem watcher lifecycle."""

from __future__ import annotations

import time

import pytest

from app.database.database import Database
from app.watcher.events import EventKind, FileSystemEvent
from app.watcher.filesystem import FileEventHandler, WatcherError, WatcherService
from app.watcher.processor import EventProcessor


class RecordingProcessor(EventProcessor):
    """Captures normalized events for assertions."""

    def __init__(self) -> None:
        self.events: list[FileSystemEvent] = []

    def process(self, event: FileSystemEvent) -> None:
        self.events.append(event)


class FakeEvent:
    """Minimal stand-in for a watchdog event (src/dest/is_directory)."""

    def __init__(self, src_path: str, dest_path: str | None = None, is_directory: bool = False) -> None:
        self.src_path = src_path
        self.dest_path = dest_path
        self.is_directory = is_directory


def _handler_with_recorder() -> tuple[RecordingProcessor, FileEventHandler]:
    recorder = RecordingProcessor()
    return recorder, FileEventHandler(recorder)


def test_handler_normalizes_created_event() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_created(FakeEvent("/tmp/a.txt"))
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event.kind == EventKind.CREATED
    assert event.src_path == "/tmp/a.txt"
    assert event.dest_path is None
    assert event.timestamp is not None


def test_handler_ignores_directory_created() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_created(FakeEvent("/tmp/folder", is_directory=True))
    assert recorder.events == []


def test_handler_ignores_directory_modified_and_deleted() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_modified(FakeEvent("/tmp/folder", is_directory=True))
    handler.on_deleted(FakeEvent("/tmp/folder", is_directory=True))
    assert recorder.events == []


def test_handler_forward_modified() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_modified(FakeEvent("/tmp/a.txt"))
    assert recorder.events[0].kind == EventKind.MODIFIED


def test_handler_forward_deleted() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_deleted(FakeEvent("/tmp/a.txt"))
    assert recorder.events[0].kind == EventKind.DELETED


def test_handler_forward_moved_with_destination() -> None:
    recorder, handler = _handler_with_recorder()
    handler.on_moved(FakeEvent("/tmp/old.txt", dest_path="/tmp/new.txt"))
    event = recorder.events[0]
    assert event.kind == EventKind.MOVED
    assert event.src_path == "/tmp/old.txt"
    assert event.dest_path == "/tmp/new.txt"


def test_event_path_prefers_destination() -> None:
    event = FileSystemEvent(
        kind=EventKind.MOVED, src_path="/o", dest_path="/n"
    )
    assert event.path == "/n"


def test_add_directory_requires_existing_directory(tmp_path) -> None:
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    with pytest.raises(WatcherError):
        service.add_directory(str(tmp_path / "missing"))
    with pytest.raises(WatcherError):
        file_path = tmp_path / "x.txt"
        file_path.write_bytes(b"x")
        service.add_directory(str(file_path))


def test_add_directory_is_idempotent(tmp_path) -> None:
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    service.add_directory(str(tmp_path))
    service.add_directory(str(tmp_path))
    assert service.watched_directories == [str(tmp_path)]


def test_watcher_start_stop_cycle(tmp_path) -> None:
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    service.add_directory(str(tmp_path))
    assert service.running is False
    service.start()
    assert service.running is True
    service.stop()
    assert service.running is False


def test_watcher_stop_without_start_is_safe(tmp_path) -> None:
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    service.stop()
    assert service.running is False


def test_watcher_remove_directory(tmp_path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    service.add_directory(str(a))
    service.add_directory(str(b))
    service.remove_directory(str(a))
    assert service.watched_directories == [str(b)]
    service.remove_directory(str(a))  # removing unknown path is a no-op


def test_watcher_status_snapshot(tmp_path) -> None:
    service = WatcherService(FileEventHandler(RecordingProcessor()))
    service.add_directory(str(tmp_path))
    snapshot = service.status()
    assert snapshot["running"] is False
    assert snapshot["watched_directories"] == [str(tmp_path)]


def test_integration_detects_creation_and_stops_cleanly(
    database: Database, tmp_path
) -> None:
    recorder = RecordingProcessor()
    service = WatcherService(FileEventHandler(recorder))
    service.add_directory(str(tmp_path))
    service.start()
    try:
        (tmp_path / "born.txt").write_bytes(b"hello")
        assert _wait_for(lambda: any(e.kind == EventKind.CREATED for e in recorder.events))
    finally:
        service.stop()
        assert service.running is False
        assert recorder.events  # at least a CREATED event was captured


def _wait_for(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False