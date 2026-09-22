"""Contract test: the real SDK sees a 529 when the pool is saturated (#7).

The single worker is pinned by a blocking engine and the queue is shrunk to one
slot, so any request beyond (running + queued) overflows and must come back as
529 — the retryable overload signal in ADR-0003. Retries are disabled on the
SDK client so the first 529 surfaces instead of being retried away. A request
served while the pool is idle still returns 200.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from typesafe_sdk import Noul, RetryPolicy, TypeSafeAPIError, TypeSafeClient

from tests.conftest import BlockingEngine, serve
from whatdo.app import create_app
from whatdo.config import ServerSettings, Settings
from whatdo.inference.fake import FakeEngine

_QUESTIONS = {"billing": Noul(instructions="Is this about billing?")}


def _no_retry_client(base_url: str) -> TypeSafeClient:
    return TypeSafeClient(
        api_key="test-key", base_url=base_url, retry=RetryPolicy(max_retries=0)
    )


def test_saturated_pool_returns_529_to_the_sdk() -> None:
    engine = BlockingEngine()
    # pool_size defaults to 1; queue_max=1 => capacity is one running + one queued.
    settings = Settings(server=ServerSettings(queue_max=1, request_timeout=30.0))

    with serve(create_app(settings=settings, engine=engine)) as base_url:
        statuses: dict[str, int | str] = {}
        lock = threading.Lock()

        def call(name: str) -> None:
            with _no_retry_client(base_url) as client:
                try:
                    client.system_one(state=name, questions=_QUESTIONS)
                    outcome: int | str = 200
                except TypeSafeAPIError as error:
                    outcome = error.status
            with lock:
                statuses[name] = outcome

        # Pin the worker first, so the extras below see a full pipeline.
        pinner = threading.Thread(target=call, args=("pinner",))
        pinner.start()
        assert engine.entered.wait(timeout=5)

        # With the worker blocked and one queue slot: exactly one extra queues,
        # the rest overflow to 529.
        extras = [threading.Thread(target=call, args=(f"extra-{i}",)) for i in range(3)]
        for thread in extras:
            thread.start()
        # The two overflowed calls return immediately; the queued one blocks.
        deadline_hit = _wait_for(
            lambda: sum(v == 529 for v in statuses.values()) >= 2, timeout=5
        )
        assert deadline_hit, f"expected two 529s, saw {statuses}"

        engine.release()
        pinner.join(timeout=10)
        for thread in extras:
            thread.join(timeout=10)

    # One running + one queued succeeded; the two overflows were rejected.
    assert statuses["pinner"] == 200
    assert sorted(statuses.values()) == [200, 200, 529, 529]


def test_idle_pool_returns_200_to_the_sdk() -> None:
    settings = Settings(server=ServerSettings(queue_max=1, request_timeout=30.0))

    with (
        serve(create_app(settings=settings, engine=FakeEngine())) as base_url,
        _no_retry_client(base_url) as client,
    ):
        response = client.system_one(state="charged twice", questions=_QUESTIONS)
    assert 0.0 <= response.nouls["billing"].noul <= 1.0


def _wait_for(predicate: Callable[[], bool], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()
