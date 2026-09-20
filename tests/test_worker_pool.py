"""Unit tests for the worker pool: readiness, overload, timeout, parallelism.

These drive the pool directly (no HTTP). Overload behaviour as seen through the
real SDK lives in ``test_contract_overload.py``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence

import pytest

from laya_server.inference.fake import FakeEngine
from laya_server.inference.pool import PoolOverloadError, PoolTimeoutError, WorkerPool
from laya_server.schemas.jev import Question
from tests.conftest import BlockingEngine

_QUESTIONS: dict[str, Question] = {}


def _pool(
    engines: Sequence[object], queue_max: int, timeout: float = 5.0
) -> WorkerPool:
    pool = WorkerPool(list(engines), queue_max=queue_max, request_timeout=timeout)  # type: ignore[arg-type]
    pool.start()
    pool.wait_ready(timeout=5)
    return pool


def test_becomes_ready_once_all_copies_load() -> None:
    pool = _pool([FakeEngine(), FakeEngine()], queue_max=4)
    try:
        assert pool.is_ready() is True
    finally:
        pool.shutdown()


class _NotReadyEngine:
    """load() succeeds but the engine reports it cannot serve."""

    def load(self) -> None:
        pass

    def is_ready(self) -> bool:
        return False

    def predict(self, state: object, questions: object) -> object:  # pragma: no cover
        raise AssertionError("should never be reached")


class _FailingLoadEngine:
    def load(self) -> None:
        raise RuntimeError("checkpoint missing")

    def is_ready(self) -> bool:  # pragma: no cover - never reached
        return False

    def predict(self, state: object, questions: object) -> object:  # pragma: no cover
        raise AssertionError("should never be reached")


def test_engine_that_never_becomes_ready_fails_readiness() -> None:
    pool = WorkerPool([_NotReadyEngine()], queue_max=1, request_timeout=5.0)  # type: ignore[list-item]
    pool.start()
    try:
        with pytest.raises(RuntimeError):
            pool.wait_ready(timeout=5)
        assert pool.is_ready() is False
    finally:
        pool.shutdown()


def test_load_failure_surfaces_through_wait_ready() -> None:
    pool = WorkerPool([_FailingLoadEngine()], queue_max=1, request_timeout=5.0)  # type: ignore[list-item]
    pool.start()
    try:
        with pytest.raises(RuntimeError):
            pool.wait_ready(timeout=5)
        assert pool.is_ready() is False
    finally:
        pool.shutdown()


def test_saturated_queue_raises_overload() -> None:
    engine = BlockingEngine()
    pool = _pool([engine], queue_max=1)
    try:
        # Occupy the single worker.
        first = pool.submit("a", _QUESTIONS)
        assert engine.entered.wait(timeout=2)
        # Fill the one queue slot, then overflow it.
        pool.submit("b", _QUESTIONS)
        with pytest.raises(PoolOverloadError):
            pool.submit("c", _QUESTIONS)
        engine.release()
        first.result(timeout=5)
    finally:
        pool.shutdown()


def test_predict_times_out_when_worker_is_busy() -> None:
    engine = BlockingEngine()
    pool = WorkerPool([engine], queue_max=1, request_timeout=0.1)  # type: ignore[list-item]
    pool.start()
    pool.wait_ready(timeout=5)
    try:
        # Occupy the worker so a second request waits past its deadline.
        busy = pool.submit("busy", _QUESTIONS)
        assert engine.entered.wait(timeout=2)
        with pytest.raises(PoolTimeoutError):
            asyncio.run(pool.predict("late", _QUESTIONS))
        engine.release()
        busy.result(timeout=5)
    finally:
        pool.shutdown()


def test_predict_returns_result_off_the_event_loop() -> None:
    pool = _pool([FakeEngine()], queue_max=4)
    try:
        result = asyncio.run(pool.predict("hello", {"q": _noul()}))
        assert 0.0 <= result.answers["q"].noul <= 1.0  # type: ignore[union-attr]
    finally:
        pool.shutdown()


def test_copies_run_in_parallel() -> None:
    # Two blocking workers must both enter predict concurrently; if the pool
    # serialised them, only one would enter within the wait window.
    engines = [BlockingEngine(), BlockingEngine()]
    pool = _pool(engines, queue_max=2)
    try:
        pool.submit("a", _QUESTIONS)
        pool.submit("b", _QUESTIONS)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not all(
            e.entered.is_set() for e in engines
        ):
            time.sleep(0.01)
        assert all(e.entered.is_set() for e in engines)
        for engine in engines:
            engine.release()
    finally:
        pool.shutdown()


def _noul() -> Question:
    from laya_server.schemas.jev import NoulQuestion

    return NoulQuestion(instructions="billing?")
