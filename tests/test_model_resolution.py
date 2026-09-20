"""Contract tests for model resolution + /v1/models, via the real SDK (FakeEngine)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from typesafe_sdk import Noul, TypeSafeClient, TypeSafeUnprocessableEntityError

from laya_server.app import create_app
from laya_server.config import ModelSettings, Settings
from laya_server.inference.fake import FakeEngine
from tests.conftest import serve

_QUESTIONS = {"billing": Noul(instructions="Is this about billing?")}


@contextmanager
def _client(model_settings: ModelSettings) -> Iterator[TypeSafeClient]:
    settings = Settings(model=model_settings)
    with (
        serve(create_app(settings=settings, engine=FakeEngine())) as url,
        TypeSafeClient(api_key="test-key", base_url=url) as client,
    ):
        yield client


def test_jev_latest_shim_resolves_to_served_model() -> None:
    with _client(ModelSettings(served_model="laya-typed-decisions")) as client:
        # SDK default model is jev-latest.
        response = client.system_one(state="hi", questions=_QUESTIONS)
    assert response.model == "laya-typed-decisions"


def test_auto_requested_directly_is_echoed() -> None:
    with _client(ModelSettings(served_model="auto")) as client:
        response = client.system_one(state="hi", questions=_QUESTIONS, model="auto")
    assert response.model == "auto"


def test_served_model_requested_directly_is_echoed() -> None:
    with _client(ModelSettings(served_model="laya-multilingual")) as client:
        response = client.system_one(
            state="hi", questions=_QUESTIONS, model="laya-multilingual"
        )
    assert response.model == "laya-multilingual"


def test_non_served_model_is_422() -> None:
    with (
        _client(ModelSettings(served_model="auto")) as client,
        pytest.raises(TypeSafeUnprocessableEntityError),
    ):
        client.system_one(state="hi", questions=_QUESTIONS, model="laya-multilingual")


def test_alias_table_disabled_rejects_alias() -> None:
    settings = ModelSettings(served_model="auto", alias_table={"jev-1.13.0": "auto"})
    with (
        _client(settings) as client,
        pytest.raises(TypeSafeUnprocessableEntityError),
    ):
        client.system_one(state="hi", questions=_QUESTIONS, model="jev-1.13.0")


def test_alias_table_enabled_resolves_alias() -> None:
    settings = ModelSettings(
        served_model="auto",
        alias_table_enabled=True,
        alias_table={"jev-1.13.0": "auto"},
    )
    with _client(settings) as client:
        response = client.system_one(
            state="hi", questions=_QUESTIONS, model="jev-1.13.0"
        )
    assert response.model == "auto"


def test_list_models_advertises_served_model_and_shim() -> None:
    with _client(ModelSettings(served_model="auto")) as client:
        listed = client.models.list()
    names = {entry.name for entry in listed.models}
    assert "auto" in names
    assert {"jev-latest", "jev-preview"} <= names
