# Configuration

All configuration is read from environment variables via Pydantic settings.
Every variable is `WHATDO_`-prefixed, and nested groups are addressed with a `__`
(double-underscore) delimiter.

```bash
WHATDO_SERVER__PORT=9000              # server.port
WHATDO_MODEL__ENGINE=laya             # model.engine
WHATDO_MODEL__SERVED_MODEL=auto       # model.served_model
WHATDO_AUTH__ENABLED=true             # auth.enabled
WHATDO_AUTH__API_KEYS='["k1","k2"]'   # auth.api_keys (JSON list)
WHATDO_OTEL__ENABLED=true             # otel.enabled
```

## Groups at a glance

| Group | Purpose |
| ----- | ------- |
| `server` | HTTP host/port and the inference-dispatch pool (size, queue bound, request timeout). |
| `model` | Which **Checkpoint** backs the engine, the **Served Model** id, device placement, and the optional **Alias Table**. |
| `auth` | Bearer-token auth toggle and the accepted API keys. |
| `otel` | Optional OpenTelemetry master + per-signal toggles, OTLP endpoint, service name. See [Observability](observability.md). |
| `logging` | Log level and JSON-vs-plain formatting. |

!!! tip "Engine selection"
    `WHATDO_MODEL__ENGINE` chooses the backend: `fake` (default) is the
    deterministic, GPU-free **FakeEngine** used for local dev and CI; `laya`
    runs the real **Laya** engine and needs the `whatdo[laya]` extra and,
    ideally, a GPU. The container images default to `laya`.

## Settings reference

The fields, types, and defaults below are generated from the settings models.

::: whatdo.config.Settings

::: whatdo.config.ServerSettings

::: whatdo.config.ModelSettings

::: whatdo.config.AuthSettings

::: whatdo.config.OtelSettings

::: whatdo.config.LoggingSettings
