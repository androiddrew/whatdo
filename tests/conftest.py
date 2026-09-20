"""Shared test fixtures and helpers.

`serve` boots the app on a real ephemeral port in a background thread so the
official Typesafe SDK (which makes real HTTP calls via httpx2) can drive it.
This is the reusable contract-test harness referenced by tickets #3 and #4.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import uvicorn
from fastapi import FastAPI
from typesafe_sdk import TypeSafeClient

from laya_server.app import create_app
from laya_server.inference.fake import FakeEngine


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
    """The official Typesafe SDK, pointed at the live test server."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("TYPESAFE_BASE_URL", live_server)
    with TypeSafeClient() as client:
        yield client
