"""The System One endpoint: ``POST /v1/systemone``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from laya_server.api.dependencies import get_engine, get_settings
from laya_server.config import Settings
from laya_server.inference.base import DecisionEngine
from laya_server.resolution import ModelNotServedError, resolve_model
from laya_server.schemas.jev import SystemOneRequest, SystemOneResponse, Usage

router = APIRouter(prefix="/v1", tags=["system-one"])


@router.post("/systemone", response_model=SystemOneResponse)
async def system_one(
    body: SystemOneRequest,
    engine: Annotated[DecisionEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemOneResponse:
    try:
        resolved_model = resolve_model(body.model, settings.model)
    except ModelNotServedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    result = await run_in_threadpool(engine.predict, body.state, body.questions)
    return SystemOneResponse(
        # Echo the concrete resolved model id so clients can pin (ADR-0004).
        model=resolved_model,
        answers=result.answers,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=0),
    )
