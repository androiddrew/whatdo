"""The System One endpoint: ``POST /v1/systemone``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from laya_server.api.dependencies import get_engine
from laya_server.inference.base import DecisionEngine
from laya_server.schemas.jev import SystemOneRequest, SystemOneResponse, Usage

router = APIRouter(prefix="/v1", tags=["system-one"])


@router.post("/systemone", response_model=SystemOneResponse)
async def system_one(
    body: SystemOneRequest,
    engine: Annotated[DecisionEngine, Depends(get_engine)],
) -> SystemOneResponse:
    result = await run_in_threadpool(engine.predict, body.state, body.questions)
    return SystemOneResponse(
        # Echoed for now; the shim/alias resolution and 422-for-unserved-model
        # behaviour arrive in ticket #4.
        model=body.model,
        answers=result.answers,
        usage=Usage(input_tokens=result.input_tokens, output_tokens=0),
    )
