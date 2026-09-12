"""Phase 18 tests: error handling middleware and schemas."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app


def _client(tmp_path) -> TestClient:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'error_test.db'}"
    app = create_app(config)
    return TestClient(app)


def test_404_returns_structured_error(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "http_error"
        assert "message" in body
        assert "request_id" in body


def test_validation_error_structure(tmp_path) -> None:
    with _client(tmp_path) as client:
        # Missing required query param 'q'
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["message"] == "Request validation failed"
        assert "details" in body
        assert isinstance(body["details"], list)
        assert "request_id" in body


def test_invalid_query_param_structure(tmp_path) -> None:
    with _client(tmp_path) as client:
        # limit must be >= 1
        resp = client.get("/api/v1/deaths?limit=0")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"
        assert any("limit" in d.get("field", "") for d in body["details"])


def test_deaths_404_structure(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/deaths/999999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "http_error"
        assert "request_id" in body


def test_search_empty_query_rejected(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"


def test_settings_patch_invalid_bool(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.patch("/api/v1/settings", json={"ai_epitaphs_enabled": "not-a-bool"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"


def test_error_response_contains_request_id(tmp_path) -> None:
    with _client(tmp_path) as client:
        resp = client.get("/api/v1/nonexistent")
        assert "request_id" in resp.json()
        # Request ID should be present in all error responses
        assert len(resp.json()["request_id"]) > 0