"""Phase 3 tests: metadata extraction without reading file contents."""

from __future__ import annotations

import os
import stat

import pytest

from app.services.metadata_service import (
    MetadataService,
    extension_of,
    filesystem_id_of,
)


@pytest.fixture
def metadata() -> MetadataService:
    return MetadataService()


def test_extract_pulls_all_fields(metadata: MetadataService, tmp_path) -> None:
    target = tmp_path / "report_final2.pdf"
    target.write_bytes(b"x" * 512)

    meta = metadata.extract(str(target))

    assert meta.filename == "report_final2.pdf"
    assert meta.extension == ".pdf"
    assert meta.path == str(target)
    assert meta.size_bytes == 512
    assert meta.modified_at is not None
    assert meta.filesystem_id is not None


def test_extract_sizes_track_content_length(metadata: MetadataService, tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_bytes(b"hello world" * 100)

    meta = metadata.extract(str(target))
    assert meta.size_bytes == os.path.getsize(target)


def test_extension_of_variants() -> None:
    assert extension_of("archive.tar.gz") == ".gz"
    assert extension_of("notes.txt") == ".txt"
    assert extension_of("Makefile") == ""
    assert extension_of(".bashrc") == ""
    assert extension_of("noext_") == ""
    assert extension_of("photo.PNG") == ".PNG"


def test_extract_file_without_extension(metadata: MetadataService, tmp_path) -> None:
    target = tmp_path / "Makefile"
    target.write_text("all:\n", encoding="utf-8")

    meta = metadata.extract(str(target))
    assert meta.extension == ""


def test_extract_dotfile_has_no_extension(metadata: MetadataService, tmp_path) -> None:
    target = tmp_path / ".gitignore_"
    target.write_text("x\n", encoding="utf-8")

    meta = metadata.extract(str(target))
    assert meta.extension == ""


def test_extract_missing_path_raises(metadata: MetadataService, tmp_path) -> None:
    missing = tmp_path / "does_not_exist.txt"
    with pytest.raises(OSError):
        metadata.extract(str(missing))


def test_try_extract_returns_none_for_missing_path(metadata: MetadataService, tmp_path) -> None:
    missing = tmp_path / "does_not_exist.txt"
    assert metadata.try_extract(str(missing)) is None


def test_extract_works_on_directory(metadata: MetadataService, tmp_path) -> None:
    directory = tmp_path / "a_directory"
    directory.mkdir()
    meta = metadata.extract(str(directory))
    assert meta.filename == "a_directory"
    assert meta.extension == ""
    assert meta.size_bytes >= 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_extract_works_when_content_is_unreadable(
    metadata: MetadataService, tmp_path
) -> None:
    """Stat metadata must be extractable even when the content is unreadable.

    This proves the service never opens/reads file contents: a content-reading
    implementation would fail on an unreadable file.
    """
    target = tmp_path / "secret.txt"
    target.write_bytes(b"top secret")
    target.chmod(0o000)
    try:
        meta = metadata.extract(str(target))
        assert meta.size_bytes == 10
    finally:
        target.chmod(0o600)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_extract_unreadable_parent_dir_returns_none(
    metadata: MetadataService, tmp_path
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    target = locked / "x.txt"
    target.write_bytes(b"x")
    locked.chmod(0o000)
    try:
        assert metadata.try_extract(str(target)) is None
    finally:
        locked.chmod(0o700)


def test_filesystem_id_stable_for_same_file(metadata: MetadataService, tmp_path) -> None:
    target = tmp_path / "same.txt"
    target.write_bytes(b"s")
    first = metadata.extract(str(target)).filesystem_id
    second = metadata.extract(str(target)).filesystem_id
    assert first is not None
    assert first == second


def test_modified_at_is_recent_and_naive_utc(metadata: MetadataService, tmp_path) -> None:
    import datetime as dt

    target = tmp_path / "recent.txt"
    target.write_bytes(b"r")
    meta = metadata.extract(str(target))
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    assert meta.modified_at is not None
    assert abs((now - meta.modified_at).total_seconds()) < 60
    assert meta.modified_at.tzinfo is None


def test_creation_time_never_uses_ctime_on_posix(metadata: MetadataService, tmp_path) -> None:
    """On POSIX st_ctime (change time) must NOT be reported as creation time."""
    if os.name == "nt":
        pytest.skip("Windows st_ctime is a valid creation time")
    target = tmp_path / "ctime.txt"
    target.write_bytes(b"c")
    meta = metadata.extract(str(target))
    st = os.lstat(target)
    if hasattr(st, "st_birthtime"):
        assert meta.created_at is not None
    else:
        assert meta.created_at is None