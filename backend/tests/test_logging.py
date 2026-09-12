"""Phase 19 tests: logging configuration and request logging."""

from __future__ import annotations

import json
import logging
import os
import sys
from io import StringIO

from app.config import Config
from app.logging_config import JSONFormatter, setup_logging
from app.main import create_app
from fastapi.testclient import TestClient


def test_log_format_text_default(tmp_path) -> None:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'log_test.db'}"
    config.log_format = "text"
    config.log_level = "DEBUG"

    stream = StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    logger = logging.getLogger("test.logger")
    logger.info("hello world")

    output = stream.getvalue()
    assert "INFO" in output
    assert "test.logger" in output
    assert "hello world" in output


def test_json_formatter_includes_request_id() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc123"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["request_id"] == "abc123"
    assert data["message"] == "test message"
    assert data["level"] == "INFO"


def test_json_formatter_without_request_id() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=1,
        msg="no request id",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert "request_id" not in data or data.get("request_id") is None


def test_config_parses_log_format(monkeypatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "json")
    config = Config(env_file=None)
    assert config.log_format == "json"

    monkeypatch.setenv("LOG_FORMAT", "TEXT")
    config2 = Config(env_file=None)
    assert config2.log_format == "text"


def test_request_logging_middleware_adds_request_id(tmp_path) -> None:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'req_log.db'}"
    config.log_format = "text"
    app = create_app(config)
    client = TestClient(app)

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) > 0


def test_request_logging_outputs_line(tmp_path) -> None:
    config = Config(env_file=None)
    config.database_url = f"sqlite:///{tmp_path / 'req_log2.db'}"
    config.log_level = "INFO"
    config.log_format = "text"
    app = create_app(config)
    client = TestClient(app)

    # Capture logs
    stream = StringIO()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    client.get("/api/v1/health")
    output = stream.getvalue()
    assert "GET /api/v1/health 200" in output
    assert "req_id=" in output