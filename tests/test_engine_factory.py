"""The engine factory selects and replicates the right engine from settings."""

from __future__ import annotations

import pytest

from whatdo.config import ModelSettings, ServerSettings, Settings
from whatdo.inference import factory
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


@pytest.fixture
def mps_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend to be an Apple-silicon host: auto and "mps" resolve to MPS."""
    monkeypatch.setattr(
        factory,
        "resolves_to_mps",
        lambda device: device is None or device.startswith("mps"),
    )


def _laya(pool_size: int, **model: object) -> Settings:
    return Settings(
        server=ServerSettings(pool_size=pool_size),
        model=ModelSettings(engine="laya", **model),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    "model",
    [
        {},
        {"device": "mps"},
        {"device_map": ["mps", "mps:0", "cpu"]},
        # Round-robin: mps, cpu, mps.
        {"device_map": ["mps", "cpu"]},
    ],
    ids=["auto", "explicit", "device-map", "device-map-wraps"],
)
def test_rejects_more_than_one_copy_on_mps(
    mps_host: None, model: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="MPS device, which supports only one worker"):
        build_engines(_laya(3, **model))


@pytest.mark.parametrize(
    ("pool_size", "model"),
    [(1, {}), (3, {"device": "cpu"}), (3, {"device_map": ["mps", "cpu", "cpu"]})],
    ids=["single-worker", "all-cpu", "one-mps-rest-cpu"],
)
def test_allows_at_most_one_copy_on_mps(
    mps_host: None, pool_size: int, model: dict[str, object]
) -> None:
    assert len(build_engines(_laya(pool_size, **model))) == pool_size


def test_fake_engine_ignores_the_mps_limit(mps_host: None) -> None:
    assert len(build_engines(Settings(server=ServerSettings(pool_size=3)))) == 3


def test_rejection_suggests_a_device_map_that_passes(mps_host: None) -> None:
    with pytest.raises(ValueError) as rejected:
        build_engines(_laya(3))
    assert 'WHATDO_MODEL__DEVICE_MAP=\'["mps", "cpu", "cpu"]\'' in str(rejected.value)
    assert len(build_engines(_laya(3, device_map=["mps", "cpu", "cpu"]))) == 3
