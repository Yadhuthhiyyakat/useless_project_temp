"""Phase 11 tests: deterministic cemetery plot assignment."""

from __future__ import annotations

from app.database.repositories import DeathRepository
from app.services.cemetery_service import (
    CEMETERY_SIZE,
    coordinates_for_death,
    deterministic_coordinates,
    is_valid_coordinate,
)
from app.services.file_lifecycle import FileLifecycleService


def test_deterministic_coordinates_are_stable() -> None:
    a = deterministic_coordinates(key="1:/tmp/a.txt")
    b = deterministic_coordinates(key="1:/tmp/a.txt")
    assert a == b


def test_different_keys_scatter() -> None:
    a = deterministic_coordinates(key="1:/tmp/a.txt")
    b = deterministic_coordinates(key="2:/tmp/b.txt")
    assert a != b


def test_coordinates_in_bounds() -> None:
    for key in ["1:/a", "2:/b", "99:/very/long/path/with/many/components.txt"]:
        x, y = deterministic_coordinates(key=key)
        assert 0.0 <= x < CEMETERY_SIZE
        assert 0.0 <= y < CEMETERY_SIZE
        assert is_valid_coordinate(x)
        assert is_valid_coordinate(y)


def test_coordinates_for_death_uses_canonical_key() -> None:
    direct = deterministic_coordinates(key="42:/tmp/foo.txt")
    via_helper = coordinates_for_death(file_id=42, original_path="/tmp/foo.txt")
    assert direct == via_helper


def test_lifecycle_assigns_non_zero_plot(database, tmp_path) -> None:
    target = tmp_path / "buried.txt"
    target.write_bytes(b"x")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(target))

    expected_x, expected_y = coordinates_for_death(
        file_id=1, original_path=str(target)
    )
    # file_id is 1 in a fresh DB, but fetch it to be robust
    from app.database.repositories import FileRepository

    with database.session() as session:
        file_id = FileRepository(session).get_alive_by_path(str(target)).id
        expected_x, expected_y = coordinates_for_death(
            file_id=file_id, original_path=str(target)
        )

    target.unlink()
    outcome = lifecycle.confirm_deletion(str(target))

    assert outcome.recorded is True
    assert outcome.death is not None
    assert outcome.death.cemetery_x == expected_x
    assert outcome.death.cemetery_y == expected_y
    assert 0.0 <= outcome.death.cemetery_x < CEMETERY_SIZE
    assert 0.0 <= outcome.death.cemetery_y < CEMETERY_SIZE


def test_different_files_get_different_plots(database, tmp_path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    lifecycle = FileLifecycleService(database)
    lifecycle.register(str(a))
    lifecycle.register(str(b))
    a.unlink()
    b.unlink()
    da = lifecycle.confirm_deletion(str(a))
    db = lifecycle.confirm_deletion(str(b))
    assert (da.death.cemetery_x, da.death.cemetery_y) != (
        db.death.cemetery_x,
        db.death.cemetery_y,
    )


def test_same_path_different_lives_get_same_plot_if_same_id() -> None:
    # The plot is keyed by file_id + path, so a reborn file (new id) at the
    # same path gets a *different* plot — each death is unique.
    assert deterministic_coordinates(key="1:/tmp/same.txt") != deterministic_coordinates(
        key="2:/tmp/same.txt"
    )
