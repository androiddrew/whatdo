"""Unit tests for Model -> served-model resolution (ADR-0004)."""

from __future__ import annotations

import pytest

from whatdo.config import ModelSettings
from whatdo.resolution import ModelNotServedError, accepted_models, resolve_model


def test_shim_maps_jev_aliases_to_served_model() -> None:
    settings = ModelSettings(served_model="laya-typed-decisions")
    assert resolve_model("jev-latest", settings) == "laya-typed-decisions"
    assert resolve_model("jev-preview", settings) == "laya-typed-decisions"


def test_shim_works_regardless_of_alias_flag() -> None:
    # alias table disabled (default) — the shim is always on.
    settings = ModelSettings(served_model="laya")
    assert resolve_model("jev-latest", settings) == "laya"


def test_served_model_accepted_directly() -> None:
    assert resolve_model("auto", ModelSettings(served_model="auto")) == "auto"
    assert (
        resolve_model(
            "laya-multilingual", ModelSettings(served_model="laya-multilingual")
        )
        == "laya-multilingual"
    )


def test_non_served_model_raises() -> None:
    settings = ModelSettings(served_model="auto")
    with pytest.raises(ModelNotServedError):
        resolve_model("laya-multilingual", settings)


def test_alias_table_ignored_when_disabled() -> None:
    settings = ModelSettings(served_model="auto", alias_table={"jev-1.13.0": "auto"})
    with pytest.raises(ModelNotServedError):
        resolve_model("jev-1.13.0", settings)


def test_alias_table_resolves_when_enabled() -> None:
    settings = ModelSettings(
        served_model="auto",
        alias_table_enabled=True,
        alias_table={"jev-1.13.0": "auto"},
    )
    assert resolve_model("jev-1.13.0", settings) == "auto"


def test_alias_target_must_match_served_model() -> None:
    # A misconfigured alias pointing at a non-served model must not be accepted.
    settings = ModelSettings(
        served_model="auto",
        alias_table_enabled=True,
        alias_table={"foo": "laya-other"},
    )
    with pytest.raises(ModelNotServedError):
        resolve_model("foo", settings)


def test_accepted_models_is_the_single_authority() -> None:
    settings = ModelSettings(
        served_model="auto",
        alias_table_enabled=True,
        alias_table={"good": "auto", "bad": "laya-other"},
    )
    accepted = accepted_models(settings)
    assert "auto" in accepted
    assert {"jev-latest", "jev-preview"} <= set(accepted)
    assert "good" in accepted  # targets the served model
    assert "bad" not in accepted  # does not
