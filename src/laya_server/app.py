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
from laya_server.inference.factory import build_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: load the engine so ``/readyz`` gates on it.

    Loading runs in a worker thread so a slow, blocking model load (the real
    Laya engine) does not block the event loop.
    """
    await run_in_threadpool(app.state.engine.load)
    yield


def create_app(
    settings: Settings | None = None, engine: DecisionEngine | None = None
) -> FastAPI:
    """Build a configured FastAPI application.

    Args:
        settings: Application settings; defaults to environment-derived settings.
        engine: Inference engine; defaults to the engine selected by settings
            (``FakeEngine`` unless ``LAYA_MODEL__ENGINE=laya``).
    """
    settings = settings or Settings()
    engine = engine if engine is not None else build_engine(settings)

    app = FastAPI(title="laya-server", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine

    # Health probes are always open. The Jev endpoints get the auth dependency
    # only when auth is enabled; disabled means it is not applied at all (#6).
    jev_dependencies = [Depends(require_api_key)] if settings.auth.enabled else []
    app.include_router(health.router)
    app.include_router(systemone.router, dependencies=jev_dependencies)
    app.include_router(models.router, dependencies=jev_dependencies)

    return app


app = create_app()
