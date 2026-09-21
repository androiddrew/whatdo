"""Application configuration via Pydantic settings.

All settings are read from ``LAYA_``-prefixed environment variables, with nested
groups addressed using a ``__`` delimiter (e.g. ``LAYA_SERVER__PORT=9000``).

Only a subset of these fields is consumed today; the full shape is established
here so later tickets (inference, auth, observability) can wire into it without
reshaping configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from laya_server.inference.laya_engine import DEFAULT_CHECKPOINT


class ServerSettings(BaseModel):
    """HTTP server and inference-dispatch settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    pool_size: int = 1
    queue_max: int = 100
    request_timeout: float = 30.0


class ModelSettings(BaseModel):
    """Which model a deployment serves and how it is resolved (ADR-0004)."""

    # Which inference engine backs the service. "fake" is deterministic and
    # GPU-free (CI, local dev); "laya" runs the real engine (needs the [laya]
    # extra and, ideally, a GPU).
    engine: Literal["fake", "laya"] = "fake"
    # Laya checkpoint to load when engine == "laya". Proper served-model / alias
    # resolution over these arrives in ticket #5.
    laya_checkpoint: str = DEFAULT_CHECKPOINT
    laya_subfolder: str | None = None

    served_model: str = "auto"
    device: str | None = None
    device_map: list[str] = Field(default_factory=list)
    alias_table_enabled: bool = False
    alias_table: dict[str, str] = Field(default_factory=dict)
    hf_cache_dir: str | None = None


class AuthSettings(BaseModel):
    """Bearer-token auth settings."""

    enabled: bool = False
    api_keys: list[str] = Field(default_factory=list)


class OtelSettings(BaseModel):
    """Optional OpenTelemetry settings: a master toggle plus per-signal toggles."""

    enabled: bool = False
    traces: bool = True
    metrics: bool = True
    logs: bool = True
    endpoint: str | None = None
    service_name: str = "laya-server"


class LoggingSettings(BaseModel):
    """Application logging settings."""

    level: str = "INFO"
    json_logs: bool = True


class Settings(BaseSettings):
    """Top-level application settings, grouped by concern."""

    model_config = SettingsConfigDict(
        env_prefix="LAYA_",
        env_nested_delimiter="__",
        # `model` is a legitimate group name here; opt out of pydantic's
        # protected `model_` namespace so it doesn't warn.
        protected_namespaces=(),
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    otel: OtelSettings = Field(default_factory=OtelSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
