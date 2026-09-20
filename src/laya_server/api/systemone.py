"""The System One endpoint: ``POST /v1/systemone``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from laya_server.api.dependencies import get_pool, get_settings
from laya_server.config import Settings
from laya_server.inference.pool import PoolOverloadError, PoolTimeoutError, WorkerPool
from laya_server.resolution import ModelNotServedError, resolve_model
from laya_server.schemas.jev import SystemOneRequest, SystemOneResponse, Usage

router = APIRouter(prefix="/v1", tags=["system-one"])

# Non-standard overload status the official SDK retries with backoff (ADR-0003).
HTTP_529_OVERLOADED = 529


@router.post("/systemone", response_model=SystemOneResponse)
async def system_one(
    body: SystemOneRequest,
    pool: Annotated[WorkerPool, Depends(get_pool)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemOneResponse:
    try:
        resolved_model = resolve_model(body.model, settings.model)
    except ModelNotServedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    try:
        result = await pool.predict(body.state, body.questions)
    except PoolOverloadError as error:
        raise HTTPException(
            status_code=HTTP_529_OVERLOADED,
            detail="Server overloaded; retry after a short delay.",
        ) from error
    except PoolTimeoutError as error:
        # A request that ages out is a saturation symptom; ADR-0003 makes 529 the
        # single overload signal, so a timeout surfaces as 529 too (retryable).
        raise HTTPException(
            status_code=HTTP_529_OVERLOADED,
            detail="Server overloaded (request timed out); retry after a short delay.",
        ) from error
    return SystemOneResponse(
        # Echo the concrete resolved model id so clients can pin (ADR-0004).
        model=resolved_model,
        answers=result.answers,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=0),
    )
