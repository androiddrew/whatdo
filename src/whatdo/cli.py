"""The ``whatdo`` command line: ``whatdo serve`` starts the API server.

Each flag overrides the matching ``WHATDO_*`` environment variable; anything not
given on the command line comes from the environment, then the settings
defaults. Flags therefore default to ``None`` ("not given").
"""

from __future__ import annotations

from typing import Any

import click
import uvicorn
from pydantic import BaseModel, ValidationError

from whatdo.config import LoggingSettings, ModelSettings, ServerSettings, Settings

LOG_LEVELS = ("debug", "info", "warning", "error", "critical")


def _help(
    text: str, env: str, group: type[BaseModel], field: str, shown: str | None = None
) -> str:
    """Help text naming the equivalent environment variable and the default."""
    if shown is None:
        default = group.model_fields[field].default
        shown = "auto-detect" if default is None else str(default)
    return f"{text} [env: {env}; default: {shown}]"


def _override(model: BaseModel, **values: Any) -> Any:
    """``model`` with the given (non-``None``) values applied, re-validated."""
    given = {key: value for key, value in values.items() if value is not None}
    return type(model).model_validate({**model.model_dump(), **given})


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="whatdo")
def main() -> None:
    """whatdo: a Jev API server backed by the Laya decision engine."""


@main.command(
    epilog=(
        "Every setting can also be set with its WHATDO_* environment variable; "
        "flags take precedence. API keys are read only from the environment "
        "(WHATDO_AUTH__ENABLED, WHATDO_AUTH__API_KEYS) so they never appear in "
        "process lists or shell history."
    )
)
@click.option(
    "--host",
    help=_help("Interface to bind.", "WHATDO_SERVER__HOST", ServerSettings, "host"),
)
@click.option(
    "--port",
    type=click.IntRange(1, 65535),
    help=_help("Port to listen on.", "WHATDO_SERVER__PORT", ServerSettings, "port"),
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    help=_help(
        "Model copies serving requests in parallel (worker threads in one "
        "process). Apple's MPS device supports only one.",
        "WHATDO_SERVER__POOL_SIZE",
        ServerSettings,
        "pool_size",
    ),
)
@click.option(
    "--engine",
    type=click.Choice(["laya", "fake"]),
    help=_help(
        "Inference engine. 'fake' returns meaningless answers without a model: "
        "for testing only.",
        "WHATDO_MODEL__ENGINE",
        ModelSettings,
        "engine",
    ),
)
@click.option(
    "--device",
    help=_help(
        "Torch device for every worker, e.g. cpu, cuda, cuda:1, mps. "
        "Auto-detect tries CUDA, then MPS, then CPU.",
        "WHATDO_MODEL__DEVICE",
        ModelSettings,
        "device",
    ),
)
@click.option(
    "--checkpoint",
    help=_help(
        "Laya checkpoint: a Hugging Face repo id or a local path.",
        "WHATDO_MODEL__LAYA_CHECKPOINT",
        ModelSettings,
        "laya_checkpoint",
    ),
)
@click.option(
    "--queue-max",
    type=click.IntRange(min=1),
    help=_help(
        "Requests allowed to wait for a worker before new ones get a 529.",
        "WHATDO_SERVER__QUEUE_MAX",
        ServerSettings,
        "queue_max",
    ),
)
@click.option(
    "--request-timeout",
    type=click.FloatRange(min=0, min_open=True),
    help=_help(
        "Seconds a request may take before it gets a 529.",
        "WHATDO_SERVER__REQUEST_TIMEOUT",
        ServerSettings,
        "request_timeout",
    ),
)
@click.option(
    "--log-level",
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    help=_help(
        "Log level for whatdo and uvicorn.",
        "WHATDO_LOGGING__LEVEL",
        LoggingSettings,
        "level",
    ),
)
@click.option(
    "--json-logs/--text-logs",
    default=None,
    help=_help(
        "JSON log lines (for log collectors) or plain text (for terminals).",
        "WHATDO_LOGGING__JSON_LOGS",
        LoggingSettings,
        "json_logs",
        shown="json",
    ),
)
def serve(
    host: str | None,
    port: int | None,
    workers: int | None,
    engine: str | None,
    device: str | None,
    checkpoint: str | None,
    queue_max: int | None,
    request_timeout: float | None,
    log_level: str | None,
    json_logs: bool | None,
) -> None:
    """Start the API server."""
    # Imported here so `whatdo --help` / `--version` stay fast.
    from whatdo.app import create_app

    try:
        settings = Settings()
        settings = settings.model_copy(
            update={
                "server": _override(
                    settings.server,
                    host=host,
                    port=port,
                    pool_size=workers,
                    queue_max=queue_max,
                    request_timeout=request_timeout,
                ),
                "model": _override(
                    settings.model,
                    engine=engine,
                    device=device,
                    laya_checkpoint=checkpoint,
                ),
                "logging": _override(
                    settings.logging,
                    level=log_level.upper() if log_level else None,
                    json_logs=json_logs,
                ),
            }
        )
        app = create_app(settings=settings)
    except ValidationError as error:
        raise click.UsageError(f"invalid configuration:\n{error}") from error
    except ValueError as error:  # e.g. more than one worker on MPS
        raise click.UsageError(str(error)) from error

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.logging.level.lower(),
    )
