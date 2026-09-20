"""The models listing endpoint: ``GET /v1/models``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from laya_server.api.dependencies import get_settings
from laya_server.config import Settings
from laya_server.resolution import accepted_models
from laya_server.schemas.jev import ModelMetadata, ModelsResponse

router = APIRouter(prefix="/v1", tags=["models"])

# Placeholder release date; this server does not version its checkpoints.
_RELEASE_DATE = "2026-09-15"


@router.get("/models", response_model=ModelsResponse)
def list_models(settings: Annotated[Settings, Depends(get_settings)]) -> ModelsResponse:
    """List the model ids this deployment accepts: its served model + aliases.

    Sourced from ``accepted_models`` so the listing always matches what
    ``/v1/systemone`` will actually resolve.
    """
    served = settings.model.served_model
    entries = [
        ModelMetadata(
            name=name,
            description=(
                f"The model served by this deployment ({served})."
                if name == served
                else f"Alias for the served model ({served})."
            ),
            release_date=_RELEASE_DATE,
        )
        for name in accepted_models(settings.model)
    ]
    return ModelsResponse(models=entries)
