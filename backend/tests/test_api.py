"""Phase 1 tests: app factory, health endpoint and configuration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app


@pytest.fixture
def api_client(tmp_path):
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'api_test.db'}"
    app = create_app(config)
    with TestClient(app) as client:
        yield client


def test_create_app_boots_and_serves_health(api_client) -> None:
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_has_no_unexpected_extra_fields(api_client) -> None:
    response = api_client.get("/api/v1/health")
    assert set(response.json().keys()) == {"status"}


def test_lifespan_initializes_database(tmp_path) -> None:
    db_path = tmp_path / "api_test.db"
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{db_path}"
    app = create_app(config)
    with TestClient(app):
        assert db_path.exists()


def test_config_defaults() -> None:
    config = Config(env_file=None)
    assert config.database_url.startswith("sqlite:///")
    assert config.ai_epitaphs_enabled is False
    assert config.cors_origins == []
    assert config.log_level == "INFO"


def test_config_parses_cors_and_bool_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    monkeypatch.setenv("AI_EPITAPHS_ENABLED", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    config = Config(env_file=None)
    assert config.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    assert config.ai_epitaphs_enabled is True
    assert config.log_level == "DEBUG"


def test_config_rejects_invalid_bool_as_false(monkeypatch) -> None:
    monkeypatch.setenv("AI_EPITAPHS_ENABLED", "maybe")
    config = Config(env_file=None)
    assert config.ai_epitaphs_enabled is False


def test_config_ai_epitaphs_disabled_by_default() -> None:
    config = Config(env_file=None)
    assert config.ai_epitaphs_enabled is False