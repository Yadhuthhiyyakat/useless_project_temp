"""Phase 15 tests: search, watcher status, and settings API."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.services.file_lifecycle import FileLifecycleService


def _client(tmp_path) -> TestClient:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'search_api.db'}"
    app = create_app(config)
    return TestClient(app)


def _seed_deaths(tmp_path) -> None:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'search_api.db'}"
    from app.database.database import Database

    db = Database(config)
    db.init()
    lifecycle = FileLifecycleService(db)
    for name in ["photo.jpg", "document.pdf", "photo_2.jpg", "notes.txt"]:
        p = tmp_path / name
        p.write_bytes(b"x" * 10)
        lifecycle.register(str(p))
        p.unlink()
        time.sleep(1.1)
        lifecycle.confirm_deletion(str(p))
    db.dispose()


def test_search_empty_query_rejected(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422


def test_search_returns_matches(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/search?q=photo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "photo"
        assert body["total"] == 2
        for item in body["items"]:
            assert "photo" in item["filename"].lower()


def test_search_pagination(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/search?q=.&limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 4


def test_search_no_matches(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/search?q=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


def test_watcher_status_defaults(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/watcher/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["running"] is True  # TestClient runs lifespan
        assert body["watched_directories"] == []


def test_get_settings_defaults(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["watched_directories"] == []
        assert body["ignored_directories"] == []
        assert body["ai_epitaphs_enabled"] is False


def test_update_settings_watched_directories(tmp_path) -> None:
    watched = tmp_path / "watch1"
    ignored = tmp_path / "ignored1"
    watched.mkdir()
    ignored.mkdir()
    with _client(tmp_path) as client:
        resp = client.patch(
            "/api/v1/settings",
            json={"watched_directories": [str(watched)], "ignored_directories": [str(ignored)]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["watched_directories"] == [str(watched)]
        assert body["ignored_directories"] == [str(ignored)]

        # Verify persistence via GET
        resp2 = client.get("/api/v1/settings")
        assert resp2.json()["watched_directories"] == [str(watched)]


def test_update_settings_ai_epitaphs(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.patch("/api/v1/settings", json={"ai_epitaphs_enabled": True})
        assert resp.status_code == 200
        assert resp.json()["ai_epitaphs_enabled"] is True

        resp2 = client.patch("/api/v1/settings", json={"ai_epitaphs_enabled": False})
        assert resp2.json()["ai_epitaphs_enabled"] is False


def test_settings_partial_update_keeps_unchanged(tmp_path) -> None:
    test_dir = tmp_path / "partial_test"
    test_dir.mkdir()
    with _client(tmp_path) as client:
        client.patch("/api/v1/settings", json={"ai_epitaphs_enabled": True})
        # Only update watched_directories
        resp = client.patch("/api/v1/settings", json={"watched_directories": [str(test_dir)]})
        assert resp.json()["ai_epitaphs_enabled"] is True
        assert resp.json()["watched_directories"] == [str(test_dir)]


def test_settings_affects_watcher_status(tmp_path) -> None:
    test_dir = tmp_path / "new_watch"
    test_dir.mkdir()
    with _client(tmp_path) as client:
        watched = str(test_dir)
        client.patch("/api/v1/settings", json={"watched_directories": [watched]})
        resp = client.get("/api/v1/watcher/status")
        assert watched in resp.json()["watched_directories"]


def test_dynamic_directory_watch_and_death_recording(tmp_path) -> None:
    test_dir = tmp_path / "live_watch_test"
    test_dir.mkdir()
    with _client(tmp_path) as client:
        # User adds directory through settings API
        resp = client.patch("/api/v1/settings", json={"watched_directories": [str(test_dir)]})
        assert resp.status_code == 200

        # Create file in newly watched directory
        file_path = str(test_dir / "rip_file.txt")
        (test_dir / "rip_file.txt").write_text("farewell")
        time.sleep(0.4)

        # Delete file in newly watched directory
        (test_dir / "rip_file.txt").unlink()
        time.sleep(0.6)

        # Check death record was created and is queryable
        deaths_resp = client.get("/api/v1/deaths")
        assert deaths_resp.status_code == 200
        items = deaths_resp.json()["items"]
        assert len(items) >= 1
        assert any(item["filename"] == "rip_file.txt" for item in items)