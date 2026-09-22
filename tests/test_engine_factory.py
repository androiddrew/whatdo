"""The engine factory selects and replicates the right engine from settings."""

from __future__ import annotations

import pytest

from whatdo.config import ModelSettings, ServerSettings, Settings
from whatdo.inference.factory import (
    _resolve_devices,
    build_engine,
    build_engines,
)
from whatdo.inference.fake import FakeEngine
from whatdo.inference.laya_engine import LayaEngine


def test_defaults_to_fake_engine() -> None:
    assert isinstance(build_engine(Settings()), FakeEngine)


def test_selects_laya_engine_without_importing_laya(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHATDO_MODEL__ENGINE", "laya")
    engine = build_engine(Settings())
    assert isinstance(engine, LayaEngine)
    # Constructed but not loaded: no laya/torch import happened.
    assert engine.is_ready() is False


def test_build_engines_makes_pool_size_copies() -> None:
    settings = Settings(server=ServerSettings(pool_size=3))
    engines = build_engines(settings)
    assert len(engines) == 3
    assert all(isinstance(engine, FakeEngine) for engine in engines)


def test_build_engines_never_makes_an_empty_pool() -> None:
    settings = Settings(server=ServerSettings(pool_size=0))
    assert len(build_engines(settings)) == 1


def test_device_map_spreads_copies_round_robin() -> None:
    model = ModelSettings(device_map=["cuda:0", "cuda:1"])
    # cuda:0, cuda:1, cuda:0 — round-robin over the pinning list.
    assert _resolve_devices(model, pool_size=3) == ["cuda:0", "cuda:1", "cuda:0"]


def test_without_device_map_all_copies_use_the_default_device() -> None:
    model = ModelSettings(device="cpu")
    assert _resolve_devices(model, pool_size=2) == ["cpu", "cpu"]
