"""FastAPI application factory and lifespan.

Wires configuration, the worker pool of inference engines, the API routers,
auth, model resolution, and optional observability — all through this one
factory and lifespan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.concurrency import run_in_threadpool

from laya_server.api import health, models, systemone
from laya_server.api.auth import require_api_key
from laya_server.config import Settings
from laya_server.inference.base import DecisionEngine
from laya_server.inference.factory import build_engines
from laya_server.inference.pool import WorkerPool
from laya_server.observability import configure_observability, shutdown_observability


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: start the worker pool so ``/readyz`` gates on it.

    Starting spawns the worker threads (each loads its own engine copy) and
    then waits — off the event loop — until every copy is ready, so a slow,
    blocking model load does not block the loop. The pool is drained on exit.
    """
    pool: WorkerPool = app.state.pool
    pool.start()
    try:
        await run_in_threadpool(pool.wait_ready)
    except BaseException:
        # A failed load leaves sibling workers blocked on the queue; drain them
        # (and stop OTEL export threads) rather than leak before propagating.
        await run_in_threadpool(pool.shutdown)
        await run_in_threadpool(shutdown_observability, app)
        raise
    try:
        yield
    finally:
        await run_in_threadpool(pool.shutdown)
        # Flush and stop OTEL providers (no-op when observability is off).
        await run_in_threadpool(shutdown_observability, app)


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

    app = FastAPI(title="laya-server", lifespan=lifespan)
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
