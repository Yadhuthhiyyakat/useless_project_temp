"""Phase 13 tests: deaths REST API."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.services.file_lifecycle import FileLifecycleService


def _client(tmp_path) -> TestClient:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'deaths_api.db'}"
    app = create_app(config)
    return TestClient(app)


def _create_death_via_lifecycle(tmp_path, filename: str) -> int:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'deaths_api.db'}"
    # Reuse the same DB file the client uses — create lifecycle directly
    from app.database.database import Database

    db = Database(config)
    db.init()
    lifecycle = FileLifecycleService(db)
    target = tmp_path / filename
    target.write_bytes(b"x" * 10)
    lifecycle.register(str(target))
    target.unlink()
    outcome = lifecycle.confirm_deletion(str(target))
    db.dispose()
    assert outcome.recorded
    return outcome.death.id


def test_list_deaths_empty(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/deaths")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["limit"] == 20
        assert body["offset"] == 0


def test_create_and_list_death(tmp_path) -> None:
    with _client(tmp_path) as client:
        # create via lifecycle sharing the same DB file
        from app.database.database import Database

        config = Config(env_file=None)
        config.database_url = f"sqlite:///{tmp_path / 'deaths_api.db'}"
        db = Database(config)
        db.init()
        lifecycle = FileLifecycleService(db)
        target = tmp_path / "hello.txt"
        target.write_bytes(b"hello world")
        lifecycle.register(str(target))
        target.unlink()
        outcome = lifecycle.confirm_deletion(str(target))
        db.dispose()
        assert outcome.recorded

        resp = client.get("/api/v1/deaths")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["filename"] == "hello.txt"
        assert item["extension"] == ".txt"
        assert item["cause"] == "DELETE_DETECTED"
        assert item["cause_label"] == "Deleted"
        assert "lifespan_label" in item
        assert "epitaph" in item and item["epitaph"]
        assert "cemetery_x" in item and 0 <= item["cemetery_x"] < 100
        assert set(item.keys()) >= {
            "id",
            "file_id",
            "filename",
            "original_path",
            "extension",
            "size_bytes",
            "born_at",
            "deleted_at",
            "lifespan_seconds",
            "lifespan_label",
            "cause",
            "cause_label",
            "epitaph",
            "cemetery_x",
            "cemetery_y",
            "created_at",
        }


def test_get_death_by_id(tmp_path) -> None:
    with _client(tmp_path) as client:
        from app.database.database import Database

        config = Config(env_file=None)
        config.database_url = f"sqlite:///{tmp_path / 'deaths_api.db'}"
        db = Database(config)
        db.init()
        lifecycle = FileLifecycleService(db)
        target = tmp_path / "single.txt"
        target.write_bytes(b"x")
        lifecycle.register(str(target))
        target.unlink()
        outcome = lifecycle.confirm_deletion(str(target))
        death_id = outcome.death.id
        db.dispose()

        resp = client.get(f"/api/v1/deaths/{death_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == death_id
        assert resp.json()["filename"] == "single.txt"

        resp2 = client.get("/api/v1/deaths/999999")
        assert resp2.status_code == 404


def test_pagination_and_filters(tmp_path) -> None:
    with _client(tmp_path) as client:
        from app.database.database import Database

        config = Config(env_file=None)
        config.database_url = f"sqlite:///{tmp_path / 'deaths_api.db'}"
        db = Database(config)
        db.init()
        lifecycle = FileLifecycleService(db)
        for name in ["a.txt", "b.log", "c.txt"]:
            p = tmp_path / name
            p.write_bytes(b"x")
            lifecycle.register(str(p))
            p.unlink()
            lifecycle.confirm_deletion(str(p))
        db.dispose()

        resp = client.get("/api/v1/deaths?limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 3

        resp2 = client.get("/api/v1/deaths?limit=2&offset=2")
        assert len(resp2.json()["items"]) == 1

        resp3 = client.get("/api/v1/deaths?extension=.txt")
        assert resp3.json()["total"] == 2

        resp4 = client.get("/api/v1/deaths?q=b.log")
        assert resp4.json()["total"] == 1
        assert resp4.json()["items"][0]["filename"] == "b.log"

        resp5 = client.get("/api/v1/deaths?cause=DELETE_DETECTED")
        assert resp5.json()["total"] == 3

        resp6 = client.get("/api/v1/deaths?cause=UNKNOWN")
        assert resp6.json()["total"] == 0


def test_cors_not_enabled_by_default(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/health", headers={"Origin": "http://example.com"})
        # no CORS header when not configured
        assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}
