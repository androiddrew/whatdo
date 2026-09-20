"""Select the inference engine from settings."""

from __future__ import annotations

from laya_server.config import Settings
from laya_server.inference.base import DecisionEngine
from laya_server.inference.fake import FakeEngine
from laya_server.inference.laya_engine import LayaEngine


def build_engine(settings: Settings) -> DecisionEngine:
    """Construct the configured engine (not yet loaded)."""
    if settings.model.engine == "laya":
        return LayaEngine(
            checkpoint=settings.model.laya_checkpoint,
            device=settings.model.device,
            subfolder=settings.model.laya_subfolder,
        )
    return FakeEngine()
