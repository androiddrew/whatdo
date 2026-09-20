"""FastAPI application factory and lifespan.

Wires configuration, the inference engine, and the API routers. Auth, model
resolution, the worker pool, and observability are layered on in later tickets
via the same factory and lifespan.
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
        # rather than leak threads before propagating the startup failure.
        await run_in_threadpool(pool.shutdown)
        raise
    try:
        yield
    finally:
        await run_in_threadpool(pool.shutdown)


def create_app(
    settings: Settings | None = None,
    engine: DecisionEngine | None = None,
    engines: list[DecisionEngine] | None = None,
) -> FastAPI:
    """Build a configured FastAPI application.

    Args:
        settings: Application settings; defaults to environment-derived settings.
        engines: The engine copies backing the worker pool; defaults to
            ``pool_size`` copies selected by settings.
        engine: Convenience for injecting a single-copy pool (tests); ignored
            when ``engines`` is given.
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

    return app


app = create_app()
