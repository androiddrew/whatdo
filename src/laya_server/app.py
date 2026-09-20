"""FastAPI application factory and lifespan.

Wires configuration, the inference engine, and the API routers. Auth, model
resolution, the worker pool, and observability are layered on in later tickets
via the same factory and lifespan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from laya_server.api import health, systemone
from laya_server.config import Settings
from laya_server.inference.base import DecisionEngine
from laya_server.inference.fake import FakeEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan.

    Real model loading (and readiness gating on it) is wired in here in a later
    ticket; the engine is currently ready as soon as it is constructed.
    """
    yield


def create_app(
    settings: Settings | None = None, engine: DecisionEngine | None = None
) -> FastAPI:
    """Build a configured FastAPI application.

    Args:
        settings: Application settings; defaults to environment-derived settings.
        engine: Inference engine; defaults to the deterministic ``FakeEngine``.
            The real Laya engine and config-driven selection arrive in ticket #4.
    """
    settings = settings or Settings()
    engine = engine or FakeEngine()

    app = FastAPI(title="laya-server", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine

    app.include_router(health.router)
    app.include_router(systemone.router)

    return app


app = create_app()
