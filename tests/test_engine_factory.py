"""The engine factory selects the right engine from settings."""

from __future__ import annotations

import pytest

from laya_server.config import Settings
from laya_server.inference.factory import build_engine
from laya_server.inference.fake import FakeEngine
from laya_server.inference.laya_engine import LayaEngine


def test_defaults_to_fake_engine() -> None:
    assert isinstance(build_engine(Settings()), FakeEngine)


def test_selects_laya_engine_without_importing_laya(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LAYA_MODEL__ENGINE", "laya")
    engine = build_engine(Settings())
    assert isinstance(engine, LayaEngine)
    # Constructed but not loaded: no laya/torch import happened.
    assert engine.is_ready() is False
