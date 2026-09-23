"""FastAPI application factory and lifespan.

Wires configuration, the worker pool of inference engines, the API routers,
auth, model resolution, and optional observability — all through this one
factory and lifespan.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.concurrency import run_in_threadpool

from whatdo.api import health, models, systemone
from whatdo.api.auth import require_api_key
from whatdo.config import Settings
from whatdo.inference.base import DecisionEngine
from whatdo.inference.factory import build_engines
from whatdo.inference.pool import WorkerPool
from whatdo.observability import configure_observability, shutdown_observability

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: start the worker pool so ``/readyz`` gates on it.

    Starting spawns the worker threads (each loads its own engine copy) and
    then waits — off the event loop — until every copy is ready, so a slow,
    blocking model load does not block the loop. The pool is drained on exit.
    """
    pool: WorkerPool = app.state.pool
    _log_startup(app.state.settings, pool)
    started = time.perf_counter()
    pool.start()
    try:
        await run_in_threadpool(pool.wait_ready)
    except BaseException:
        # The worker already logged the load error; uvicorn prints the chain.
        logger.error("Startup failed: worker pool did not become ready")
        # A failed load leaves sibling workers blocked on the queue; drain them
        # (and stop OTEL export threads) rather than leak before propagating.
        await run_in_threadpool(pool.shutdown)
        await run_in_threadpool(shutdown_observability, app)
        raise
    logger.info(
        "Worker pool ready: %d engines loaded in %.1fs",
        len(pool.engines),
        time.perf_counter() - started,
    )
    try:
        yield
    finally:
        logger.info("Shutting down worker pool")
        await run_in_threadpool(pool.shutdown)
        # Flush and stop OTEL providers (no-op when observability is off).
        await run_in_threadpool(shutdown_observability, app)
        logger.info("Shutdown complete")


def _log_startup(settings: Settings, pool: WorkerPool) -> None:
    """Report what this process is about to serve (never logs API keys)."""
    model = settings.model
    otel = settings.otel
    logger.info(
        "Starting whatdo: engine=%s served_model=%s workers=%d queue_max=%d "
        "request_timeout=%.1fs auth=%s otel=%s log_level=%s",
        model.engine,
        model.served_model,
        len(pool.engines),
        settings.server.queue_max,
        settings.server.request_timeout,
        (
            f"enabled ({len(settings.auth.api_keys)} keys)"
            if settings.auth.enabled
            else "disabled"
        ),
        f"enabled ({otel.endpoint or 'default endpoint'})"
        if otel.enabled
        else "disabled",
        settings.logging.level.upper(),
    )
    # One line per copy: each engine's repr carries its own model/device, so
    # this stays accurate for injected engines and future engine types.
    for index, engine in enumerate(pool.engines):
        logger.info("Worker %d: %r", index, engine)


def create_app(
    settings: Settings | None = None,
    engine: DecisionEngine | None = None,
    engines: list[DecisionEngine] | None = None,
    *,
    otel_span_exporter: object = None,
    otel_metric_reader: object = None,
) -> FastAPI:
    """Build a configured FastAPI application.

    Args:
        settings: Application settings; defaults to environment-derived settings.
        engines: The engine copies backing the worker pool; defaults to
            ``pool_size`` copies selected by settings.
        engine: Convenience for injecting a single-copy pool (tests); ignored
            when ``engines`` is given.
        otel_span_exporter: In-memory span exporter for tests; production uses an
            OTLP exporter (see ``configure_observability``).
        otel_metric_reader: In-memory metric reader for tests; production uses an
            OTLP periodic reader.
    """
    settings = settings or Settings()
    if engines is None:
        engines = [engine] if engine is not None else build_engines(settings)
    pool = WorkerPool(
        engines,
        queue_max=settings.server.queue_max,
        request_timeout=settings.server.request_timeout,
    )

    app = FastAPI(title="whatdo", lifespan=lifespan)
    app.state.settings = settings
    app.state.pool = pool

    # Health probes are always open. The Jev endpoints get the auth dependency
    # only when auth is enabled; disabled means it is not applied at all (#6).
    jev_dependencies = [Depends(require_api_key)] if settings.auth.enabled else []
    app.include_router(health.router)
    app.include_router(systemone.router, dependencies=jev_dependencies)
    app.include_router(models.router, dependencies=jev_dependencies)

    # Configure logging + optional OTEL last, so FastAPI instrumentation sees the
    # final route set. No-op observability when otel is disabled (#8).
    app.state.telemetry = configure_observability(
        app,
        settings,
        span_exporter=otel_span_exporter,
        metric_reader=otel_metric_reader,
    )

    return app


app = create_app()
