"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from laya_server.api.dependencies import get_pool
from laya_server.inference.pool import WorkerPool

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up and serving."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(
    response: Response,
    pool: Annotated[WorkerPool, Depends(get_pool)],
) -> dict[str, str]:
    """Readiness: every engine copy in the pool is loaded and able to serve."""
    if pool.is_ready():
        return {"status": "ready"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not ready"}
