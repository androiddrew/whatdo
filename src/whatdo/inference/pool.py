"""An in-process thread worker pool with a bounded queue (ADR-0003).

``predict()`` is a synchronous torch forward pass; torch releases the GIL during
it, so ``pool_size`` model copies each run in their own worker thread and serve
in parallel. A single shared **bounded** queue (``queue_max``) feeds them, giving
predictable backpressure: when it is saturated, submission fails fast so the API
can answer 529 (overload) rather than let latency grow unbounded. Each accepted
request also carries a wall-clock timeout.

The pool is engine-agnostic: it drives anything satisfying ``DecisionEngine``,
so the deterministic ``FakeEngine`` and the real ``LayaEngine`` share this path.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass

from whatdo.inference.base import DecisionEngine, PredictResult
from whatdo.schemas.jev import JSONContent, Question

logger = logging.getLogger(__name__)


class PoolOverloadError(Exception):
    """The shared queue was saturated; the request should be retried (529)."""


class PoolTimeoutError(Exception):
    """An accepted request exceeded its wall-clock deadline before completing."""


@dataclass
class _WorkItem:
    state: JSONContent
    questions: dict[str, Question]
    future: Future[PredictResult]


class WorkerPool:
    """Runs ``predict`` on a fixed set of engine copies behind a bounded queue.

    One worker thread per engine copy; ``submit`` never blocks — it either
    enqueues immediately or raises :class:`PoolOverloadError`.
    """

    def __init__(
        self,
        engines: list[DecisionEngine],
        queue_max: int,
        request_timeout: float,
    ) -> None:
        self._engines = engines
        self._queue_max = max(1, queue_max)
        # maxsize must be >= 1 for a bounded queue (0 means "infinite" to Queue).
        self._queue: queue.Queue[_WorkItem | None] = queue.Queue(
            maxsize=self._queue_max
        )
        self._request_timeout = request_timeout
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._ready = 0
        self._load_error: BaseException | None = None
        # Set once every engine has loaded, or as soon as one fails to load.
        self._ready_event = threading.Event()

    @property
    def engines(self) -> list[DecisionEngine]:
        """The engine copies backing the pool, one per worker thread."""
        return list(self._engines)

    # -- lifecycle ---------------------------------------------------------- #
    def start(self) -> None:
        """Spawn one worker thread per engine; each loads its own copy."""
        for index, engine in enumerate(self._engines):
            thread = threading.Thread(
                target=self._run,
                args=(engine,),
                name=f"laya-worker-{index}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def wait_ready(self, timeout: float | None = None) -> None:
        """Block until every engine has loaded, or raise if one failed to.

        ``timeout`` is a safety bound (``None`` waits indefinitely, matching a
        cold model load); the caller runs this off the event loop.
        """
        if not self._ready_event.wait(timeout):
            raise TimeoutError("worker pool did not become ready in time")
        if self._load_error is not None:
            raise RuntimeError(
                "worker pool failed to load an engine"
            ) from self._load_error

    def is_ready(self) -> bool:
        with self._lock:
            return self._load_error is None and self._ready == len(self._engines)

    def queue_depth(self) -> int:
        """Approximate number of requests waiting in the shared queue."""
        return self._queue.qsize()

    def shutdown(self) -> None:
        """Drain pending work and stop every worker thread."""
        cancelled = 0
        # Cancel anything still queued so blocked callers don't wait for a
        # worker that is going away.
        while True:
            try:
                pending = self._queue.get_nowait()
            except queue.Empty:
                break
            if pending is not None and pending.future.cancel():
                cancelled += 1
            self._queue.task_done()
        # One sentinel per worker; a short timeout keeps shutdown from hanging if
        # a worker died (e.g. a load failure) and can't consume its sentinel.
        for _ in self._threads:
            # queue.Full only if a worker died (e.g. a load failure); don't hang.
            with contextlib.suppress(queue.Full):
                self._queue.put(None, timeout=1.0)
        for thread in self._threads:
            thread.join(timeout=5)
        logger.debug(
            "Worker pool stopped (%d workers, %d pending requests cancelled)",
            len(self._threads),
            cancelled,
        )
        self._threads.clear()

    # -- request path ------------------------------------------------------- #
    def submit(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> Future[PredictResult]:
        """Enqueue work, returning its future; raise if the queue is saturated."""
        future: Future[PredictResult] = Future()
        item = _WorkItem(state=state, questions=questions, future=future)
        try:
            self._queue.put_nowait(item)
        except queue.Full as error:
            logger.warning(
                "Worker pool overloaded: queue full (%d/%d); shedding request",
                self._queue.qsize(),
                self._queue_max,
            )
            raise PoolOverloadError from error
        logger.debug(
            "Enqueued request (%d questions); queue depth %d/%d",
            len(questions),
            self._queue.qsize(),
            self._queue_max,
        )
        return future

    async def predict(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> PredictResult:
        """Await one decision off the event loop, honouring the request timeout.

        Raises :class:`PoolOverloadError` if the queue is full and
        :class:`PoolTimeoutError` if the deadline passes first.
        """
        future = self.submit(state, questions)
        try:
            return await asyncio.wait_for(
                asyncio.wrap_future(future), self._request_timeout
            )
        except TimeoutError as error:
            # Cancel if still queued; a running forward pass can't be interrupted
            # but its result is simply discarded.
            future.cancel()
            logger.warning(
                "Request exceeded %.1fs timeout; queue depth %d/%d",
                self._request_timeout,
                self._queue.qsize(),
                self._queue_max,
            )
            raise PoolTimeoutError from error

    # -- worker ------------------------------------------------------------- #
    def _run(self, engine: DecisionEngine) -> None:
        logger.info("Loading engine %r", engine)
        started = time.perf_counter()
        try:
            engine.load()
            loaded = engine.is_ready()
        except BaseException as error:  # noqa: BLE001 - surfaced via wait_ready
            self._fail_load(error)
            return
        if not loaded:
            # load() returned but the engine reports it cannot serve.
            self._fail_load(RuntimeError("engine did not become ready after load"))
            return
        with self._lock:
            self._ready += 1
            ready = self._ready
            if self._ready == len(self._engines):
                self._ready_event.set()
        logger.info(
            "Engine loaded in %.1fs (%d/%d workers ready)",
            time.perf_counter() - started,
            ready,
            len(self._engines),
        )
        self._serve(engine)

    def _fail_load(self, error: BaseException) -> None:
        logger.error("Engine failed to load", exc_info=error)
        with self._lock:
            self._load_error = error
        self._ready_event.set()

    def _serve(self, engine: DecisionEngine) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:  # shutdown sentinel
                    return
                # Skip work whose caller already timed out and cancelled it.
                if not item.future.set_running_or_notify_cancel():
                    logger.debug("Skipping request cancelled while queued")
                    continue
                started = time.perf_counter()
                try:
                    result = engine.predict(item.state, item.questions)
                except BaseException as error:  # noqa: BLE001 - relayed to caller
                    logger.debug("Engine predict raised", exc_info=error)
                    item.future.set_exception(error)
                else:
                    logger.debug(
                        "Engine predict finished in %.1fms",
                        (time.perf_counter() - started) * 1000,
                    )
                    item.future.set_result(result)
            finally:
                self._queue.task_done()
