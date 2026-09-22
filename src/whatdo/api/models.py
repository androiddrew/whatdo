"""The models listing endpoint: ``GET /v1/models``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from whatdo.api.dependencies import get_settings
from whatdo.config import Settings
from whatdo.resolution import accepted_models
from whatdo.schemas.jev import ModelMetadata, ModelsResponse

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
