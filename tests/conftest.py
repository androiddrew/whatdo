"""Shared test fixtures and helpers.

`serve` boots the app on a real ephemeral port in a background thread so the
official Typesafe SDK (which makes real HTTP calls via httpx2) can drive it.
This is the reusable contract-test harness referenced by tickets #3 and #4.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import uvicorn
from fastapi import FastAPI
from typesafe_sdk import TypeSafeClient

from whatdo.app import create_app
from whatdo.config import AuthSettings, Settings
from whatdo.inference.base import PredictResult
from whatdo.inference.fake import FakeEngine
from whatdo.schemas.jev import JSONContent, NoulAnswer, Question

# The single key the auth-enabled contract fixtures accept.
AUTH_API_KEY = "contract-test-key"


class BlockingEngine:
    """A ``DecisionEngine`` whose ``predict`` blocks until released.

    Lets a test pin a worker (and thereby drive the queue to saturation)
    deterministically. Shared by the pool unit tests and the overload contract
    test.
    """

    def __init__(self) -> None:
        self.entered = threading.Event()
        self._release = threading.Event()

    def load(self) -> None:
        pass

    def is_ready(self) -> bool:
        return True

    def release(self) -> None:
        self._release.set()

    def predict(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> PredictResult:
        self.entered.set()
        self._release.wait(timeout=10)
        return PredictResult(answers={"billing": NoulAnswer(noul=0.5)}, input_tokens=1)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def whatdo_logs() -> Iterator[list[logging.LogRecord]]:
    """Records emitted on the ``whatdo`` logger tree, at DEBUG and above.

    ``caplog`` can't see these: the ``whatdo`` logger doesn't propagate to root.
    Building an app resets the logger level from its settings, so tests that
    need DEBUG records through an app configure ``logging.level="DEBUG"``.
    """
    logger = logging.getLogger("whatdo")
    handler = _ListHandler()
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


@contextmanager
def serve(app: FastAPI, startup_timeout: float = 15.0) -> Iterator[str]:
    """Run ``app`` under uvicorn on an ephemeral port and yield its base URL.

    ``startup_timeout`` covers the lifespan (engine load); the real Laya engine
    downloads and loads a checkpoint, so its callers pass a generous value.
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + startup_timeout
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover - startup failure
            server.should_exit = True
            raise RuntimeError("uvicorn did not start in time")
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture
def live_server() -> Iterator[str]:
    """A running server backed by the deterministic FakeEngine."""
    with serve(create_app(engine=FakeEngine())) as url:
        yield url


@pytest.fixture
def sdk_client(
    live_server: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TypeSafeClient]:
    """The official Typesafe SDK, pointed at the live (no-auth) test server."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("TYPESAFE_BASE_URL", live_server)
    with TypeSafeClient() as client:
        yield client


@pytest.fixture
def auth_live_server() -> Iterator[str]:
    """A running FakeEngine server with auth enabled, accepting ``AUTH_API_KEY``."""
    settings = Settings(
        auth=AuthSettings(enabled=True, api_keys=[AUTH_API_KEY]),
    )
    with serve(create_app(settings=settings, engine=FakeEngine())) as url:
        yield url
