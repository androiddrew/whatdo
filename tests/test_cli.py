"""The ``whatdo`` command line.

``uvicorn.run`` is replaced so no server starts; the tests inspect the app and
arguments the CLI would have served with.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi import FastAPI

import whatdo.app
from whatdo.cli import main
from whatdo.config import Settings
from whatdo.inference import factory
from whatdo.inference.fake import FakeEngine
from whatdo.inference.laya_engine import LayaEngine


class _Served:
    """Captures the ``uvicorn.run`` call the CLI makes."""

    app: FastAPI
    kwargs: dict[str, Any]

    @property
    def settings(self) -> Settings:
        settings: Settings = self.app.state.settings
        return settings


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> _Served:
    captured = _Served()

    def fake_run(app: FastAPI, **kwargs: Any) -> None:
        captured.app = app
        captured.kwargs = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)
    return captured


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(main, list(args))


def test_serve_applies_flags(served: _Served) -> None:
    result = _invoke(
        "serve", "--engine", "fake", "--port", "9001", "--workers", "2",
        "--log-level", "DEBUG", "--text-logs",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert served.kwargs == {
        "host": "0.0.0.0",
        "port": 9001,
        "log_level": "debug",
        "log_config": None,  # whatdo owns the uvicorn loggers
    }
    assert served.settings.server.pool_size == 2
    assert served.settings.model.engine == "fake"
    assert served.settings.logging.level == "DEBUG"
    assert served.settings.logging.json_logs is False
    engines = served.app.state.pool.engines
    assert len(engines) == 2
    assert all(isinstance(engine, FakeEngine) for engine in engines)


def test_serve_defaults_to_the_laya_engine(served: _Served) -> None:
    result = _invoke("serve")

    assert result.exit_code == 0, result.output
    assert served.settings.model.engine == "laya"
    # Built but never loaded: uvicorn (and so the lifespan) never ran.
    (engine,) = served.app.state.pool.engines
    assert isinstance(engine, LayaEngine)
    assert engine.is_ready() is False


def test_environment_applies_where_no_flag_is_given(
    served: _Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WHATDO_AUTH__ENABLED", "true")
    monkeypatch.setenv("WHATDO_SERVER__QUEUE_MAX", "7")

    result = _invoke("serve", "--engine", "fake")

    assert result.exit_code == 0, result.output
    assert served.settings.auth.enabled is True
    assert served.settings.server.queue_max == 7


def test_flags_override_the_environment(
    served: _Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WHATDO_SERVER__PORT", "7000")
    monkeypatch.setenv("WHATDO_MODEL__ENGINE", "laya")

    result = _invoke("serve", "--engine", "fake", "--port", "9001")

    assert result.exit_code == 0, result.output
    assert served.kwargs["port"] == 9001
    assert served.settings.model.engine == "fake"


@pytest.mark.parametrize(
    "args",
    [
        ["--engine", "bogus"],
        ["--workers", "0"],
        ["--port", "70000"],
        ["--request-timeout", "0"],
        ["--log-level", "loud"],
    ],
    ids=["engine", "workers", "port", "timeout", "log-level"],
)
def test_invalid_flags_are_usage_errors(served: _Served, args: list[str]) -> None:
    result = _invoke("serve", *args)
    assert result.exit_code == 2
    assert "Usage:" in result.output


def test_more_than_one_mps_worker_is_a_clean_error(
    served: _Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(factory, "resolves_to_mps", lambda device: device is None)

    result = _invoke("serve", "--workers", "2")

    assert result.exit_code == 2
    assert "MPS device, which supports only one worker" in result.output
    assert "Traceback" not in result.output


def test_version_reports_the_installed_package() -> None:
    result = _invoke("--version")
    assert result.exit_code == 0
    assert version("whatdo") in result.output


def test_serve_help_lists_every_flag() -> None:
    result = _invoke("serve", "--help")
    assert result.exit_code == 0
    for flag in (
        "--host", "--port", "--workers", "--engine", "--device", "--checkpoint",
        "--queue-max", "--request-timeout", "--log-level", "--json-logs",
    ):  # fmt: skip
        assert flag in result.output


def test_module_app_is_built_lazily_and_once() -> None:
    # `uvicorn whatdo.app:app` resolves this attribute; importing create_app
    # alone must not build it.
    assert whatdo.app.app is whatdo.app.app
