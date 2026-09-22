"""The System One endpoint: ``POST /v1/systemone``."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from whatdo.api.dependencies import get_pool, get_settings, get_telemetry
from whatdo.config import Settings
from whatdo.inference.pool import PoolOverloadError, PoolTimeoutError, WorkerPool
from whatdo.observability import Telemetry
from whatdo.resolution import ModelNotServedError, resolve_model
from whatdo.schemas.jev import SystemOneRequest, SystemOneResponse, Usage

router = APIRouter(prefix="/v1", tags=["system-one"])

# Non-standard overload status the official SDK retries with backoff (ADR-0003).
HTTP_529_OVERLOADED = 529


@router.post("/systemone", response_model=SystemOneResponse)
async def system_one(
    body: SystemOneRequest,
    pool: Annotated[WorkerPool, Depends(get_pool)],
    settings: Annotated[Settings, Depends(get_settings)],
    telemetry: Annotated[Telemetry, Depends(get_telemetry)],
) -> SystemOneResponse:
    try:
        resolved_model = resolve_model(body.model, settings.model)
    except ModelNotServedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    question_count = len(body.questions)
    started = time.perf_counter()
    try:
        with telemetry.inference_span(
            model=resolved_model, question_count=question_count
        ):
            result = await pool.predict(body.state, body.questions)
    except PoolOverloadError as error:
        telemetry.record_overload()
        raise HTTPException(
            status_code=HTTP_529_OVERLOADED,
            detail="Server overloaded; retry after a short delay.",
        ) from error
    except PoolTimeoutError as error:
        # A request that ages out is a saturation symptom; ADR-0003 makes 529 the
        # single overload signal, so a timeout surfaces as 529 too (retryable).
        telemetry.record_overload()
        raise HTTPException(
            status_code=HTTP_529_OVERLOADED,
            detail="Server overloaded (request timed out); retry after a short delay.",
        ) from error

    # Count only served requests, matching the metric's "accepted" meaning; a
    # shed request is signalled solely by the overload counter above.
    telemetry.record_inference_latency(time.perf_counter() - started)
    telemetry.record_request(model=resolved_model, question_count=question_count)

    return SystemOneResponse(
        # Echo the concrete resolved model id so clients can pin (ADR-0004).
        model=resolved_model,
        answers=result.answers,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=0),
    )
