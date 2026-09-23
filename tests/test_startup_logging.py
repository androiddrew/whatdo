"""Startup and request-path logging through the real app lifespan."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from whatdo.app import create_app
from whatdo.config import AuthSettings, LoggingSettings, Settings
from whatdo.inference.fake import FakeEngine

_API_KEY = "super-secret-key"


def _messages(records: list[logging.LogRecord], level: int) -> list[str]:
    return [r.getMessage() for r in records if r.levelno == level]


def test_startup_reports_engine_workers_and_readiness(
    whatdo_logs: list[logging.LogRecord],
) -> None:
    settings = Settings(auth=AuthSettings(enabled=True, api_keys=[_API_KEY]))
    app = create_app(settings=settings, engines=[FakeEngine(), FakeEngine()])
    with TestClient(app):
        pass

    info = _messages(whatdo_logs, logging.INFO)
    summary = next(m for m in info if m.startswith("Starting whatdo:"))
    assert "engine=fake" in summary
    assert "workers=2" in summary
    assert "auth=enabled (1 keys)" in summary
    assert "Worker 0: FakeEngine()" in info
    assert "Worker 1: FakeEngine()" in info
    assert any(m.startswith("Worker pool ready: 2 engines loaded") for m in info)
    assert "Shutdown complete" in info
    # Never leak credentials into logs.
    assert not any(_API_KEY in r.getMessage() for r in whatdo_logs)


def test_requests_log_resolution_at_debug_and_rejections_at_info(
    whatdo_logs: list[logging.LogRecord],
) -> None:
    settings = Settings(logging=LoggingSettings(level="DEBUG"))
    body = {
        "state": "hi",
        "model": "jev-latest",
        "questions": {"billing": {"type": "noul"}},
    }
    with TestClient(create_app(settings=settings, engine=FakeEngine())) as client:
        assert client.post("/v1/systemone", json=body).status_code == 200
        rejected = client.post("/v1/systemone", json={**body, "model": "nope"})
        assert rejected.status_code == 422

    debug = _messages(whatdo_logs, logging.DEBUG)
    assert any(m.startswith("System One: model 'jev-latest' -> 'auto'") for m in debug)
    assert any(m.startswith("Fake predict:") for m in debug)
    assert "Rejected request for model 'nope' (this deployment serves 'auto')" in (
        _messages(whatdo_logs, logging.INFO)
    )
