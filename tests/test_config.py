import pytest

from whatdo.config import Settings


def test_settings_have_sensible_defaults() -> None:
    settings = Settings()

    assert settings.server.port == 8000
    assert settings.server.pool_size == 1
    assert settings.model.served_model == "auto"
    assert settings.auth.enabled is False
    assert settings.otel.enabled is False


def test_settings_read_nested_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAYA_SERVER__PORT", "9001")
    monkeypatch.setenv("LAYA_AUTH__ENABLED", "true")

    settings = Settings()

    assert settings.server.port == 9001
    assert settings.auth.enabled is True
