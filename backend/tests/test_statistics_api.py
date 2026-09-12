"""Phase 14 tests: statistics and timeline API."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app
from app.services.file_lifecycle import FileLifecycleService


def _client(tmp_path) -> TestClient:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'stats_api.db'}"
    app = create_app(config)
    return TestClient(app)


def _seed_deaths(tmp_path) -> None:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'stats_api.db'}"
    from app.database.database import Database

    db = Database(config)
    db.init()
    lifecycle = FileLifecycleService(db)
    for name in ["a.txt", "b.log", "c.txt", "d.py"]:
        p = tmp_path / name
        p.write_bytes(b"x" * 10)
        lifecycle.register(str(p))
        p.unlink()
        time.sleep(1.1)  # ensure >1 second lifespan
        lifecycle.confirm_deletion(str(p))
    db.dispose()


def test_statistics_empty(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/statistics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_deaths"] == 0
        assert body["total_lifespan_seconds"] == 0
        assert body["average_lifespan_seconds"] == 0
        assert body["by_cause"] == {}
        assert body["by_extension"] == {}
        assert body["oldest_death"] is None
        assert body["newest_death"] is None


def test_statistics_with_data(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/statistics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_deaths"] == 4
        assert body["total_lifespan_seconds"] > 0
        assert body["average_lifespan_seconds"] > 0
        assert body["by_cause"] == {"DELETE_DETECTED": 4}
        assert ".txt" in body["by_extension"]
        assert ".log" in body["by_extension"]
        assert body["oldest_death"] is not None
        assert body["newest_death"] is not None


def test_timeline_pagination(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/timeline?limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["events"]) == 2
        assert resp.json()["total"] == 4

        resp2 = client.get("/api/v1/timeline?limit=2&offset=2")
        assert len(resp2.json()["events"]) == 2

        resp3 = client.get("/api/v1/timeline?limit=10&offset=10")
        assert resp3.json()["events"] == []


def test_timeline_date_range(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        # All deaths have same timestamp; range covering them returns all
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        from_time = now - timedelta(hours=1)
        to_time = now + timedelta(hours=1)
        resp = client.get(
            f"/api/v1/timeline?from={from_time.isoformat()}&to={to_time.isoformat()}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

        # Range in the future returns empty
        future_from = now + timedelta(days=1)
        future_to = now + timedelta(days=2)
        resp2 = client.get(
            f"/api/v1/timeline?from={future_from.isoformat()}&to={future_to.isoformat()}"
        )
        assert resp2.json()["total"] == 0


def test_timeline_event_shape(tmp_path) -> None:
    _seed_deaths(tmp_path)
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/timeline")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 4
        e = events[0]
        assert set(e.keys()) >= {
            "id",
            "file_id",
            "filename",
            "extension",
            "deleted_at",
            "cause",
            "cause_label",
            "lifespan_label",
            "cemetery_x",
            "cemetery_y",
        }
        assert e["cause_label"] == "Deleted"
        assert "second" in e["lifespan_label"] or "minute" in e["lifespan_label"]