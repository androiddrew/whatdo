"""FastAPI application factory and lifespan.

This ticket establishes the bootable skeleton: an app factory, a lifespan hook,
and a liveness endpoint. Model loading, the Jev API, auth, and observability are
layered on in later tickets via the same factory and lifespan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from laya_server.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan.

    Model loading and readiness will be wired in here in later tickets; for now
    it is a no-op placeholder so the shape is in place.
    """
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""
    settings = settings or Settings()

    app = FastAPI(title="laya-server", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe: the process is up and serving."""
        return {"status": "ok"}

    return app


app = create_app()
