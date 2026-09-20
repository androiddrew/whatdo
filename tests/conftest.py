"""Shared test fixtures.

`live_server` boots the app on a real ephemeral port in a background thread so
the official Typesafe SDK (which makes real HTTP calls via httpx2) can drive it.
This is the reusable contract-test harness referenced by ticket #3.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from typesafe_sdk import TypeSafeClient

from laya_server.app import create_app
from laya_server.inference.fake import FakeEngine


@pytest.fixture
def live_server() -> Iterator[str]:
    """Run the app (with the deterministic FakeEngine) and yield its base URL."""
    app = create_app(engine=FakeEngine())
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover - startup failure
            raise RuntimeError("uvicorn did not start in time")
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture
def sdk_client(
    live_server: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TypeSafeClient]:
    """The official Typesafe SDK, pointed at the live test server."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("TYPESAFE_BASE_URL", live_server)
    with TypeSafeClient() as client:
        yield client
