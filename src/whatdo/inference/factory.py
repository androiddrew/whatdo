"""Select and replicate the inference engine from settings."""

from __future__ import annotations

from whatdo.config import ModelSettings, Settings
from whatdo.inference.base import DecisionEngine
from whatdo.inference.fake import FakeEngine
from whatdo.inference.laya_engine import LayaEngine


def build_engine(settings: Settings, device: str | None = None) -> DecisionEngine:
    """Construct the configured engine (not yet loaded).

    ``device`` overrides ``settings.model.device`` for this copy, so a pool can
    pin copies to distinct devices (ADR-0003).
    """
    if settings.model.engine == "laya":
        return LayaEngine(
            checkpoint=settings.model.laya_checkpoint,
            device=device if device is not None else settings.model.device,
            subfolder=settings.model.laya_subfolder,
        )
    return FakeEngine()


def build_engines(settings: Settings) -> list[DecisionEngine]:
    """Construct ``pool_size`` engine copies for the worker pool (ADR-0003).

    With a device-pinning list configured, copies are spread across those
    devices round-robin; otherwise every copy uses the single configured
    (auto-detected when unset) device.
    """
    pool_size = max(1, settings.server.pool_size)
    devices = _resolve_devices(settings.model, pool_size)
    return [build_engine(settings, device=devices[index]) for index in range(pool_size)]


def _resolve_devices(model: ModelSettings, pool_size: int) -> list[str | None]:
    """One device per copy: round-robin over ``device_map`` if set, else the default."""
    if model.device_map:
        return [
            model.device_map[index % len(model.device_map)]
            for index in range(pool_size)
        ]
    return [model.device] * pool_size
