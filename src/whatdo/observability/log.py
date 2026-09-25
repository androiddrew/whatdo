"""Structured JSON logging, optionally correlated with trace context (#8).

The formatter takes an injected ``trace_context`` callable so this module never
imports OpenTelemetry: when tracing is on, setup passes a callable that reads the
current span; otherwise it is ``None`` and logs simply carry no trace ids.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

# Returns the current trace/span ids to merge into each record, or None if there
# is no active, recording span.
TraceContextProvider = Callable[[], "dict[str, str] | None"]

_LAYA_HANDLER_FLAG = "_laya_json_handler"

# Plain-text layout for local development (``json_logs=False``). The thread name
# identifies which worker (``laya-worker-N``) emitted an engine/pool record.
TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(threadName)s] %(message)s"


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line, with optional trace ids."""

    def __init__(self, trace_context: TraceContextProvider | None = None) -> None:
        super().__init__()
        self._trace_context = trace_context

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if self._trace_context is not None:
            context = self._trace_context()
            if context:
                payload.update(context)
        return json.dumps(payload, default=str)


def configure_logging(
    *,
    level: str,
    json_logs: bool,
    trace_context: TraceContextProvider | None = None,
) -> None:
    """Route whatdo, uvicorn and HF library logs through one handler (idempotent).

    Uses dedicated loggers (not root) so repeated app builds in tests don't
    stack handlers and pytest's own logging is left alone. This mutates
    process-global loggers, so building two apps with different logging settings
    in one process is last-writer-wins — fine for the single-app deployment.
    """
    handler = logging.StreamHandler()
    setattr(handler, _LAYA_HANDLER_FLAG, True)
    if json_logs:
        handler.setFormatter(JsonFormatter(trace_context=trace_context))
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))

    for name in ("whatdo", "uvicorn"):
        logger = logging.getLogger(name)
        logger.setLevel(level.upper())
        _install_handler(logger, handler)

    # uvicorn's own dictConfig (when launched as ``uvicorn whatdo.app:app``)
    # gives these children plain-text handlers; drop them so records propagate
    # to the ``uvicorn`` handler above instead.
    for name in ("uvicorn.error", "uvicorn.access"):
        child = logging.getLogger(name)
        for existing in list(child.handlers):
            child.removeHandler(existing)
        child.propagate = True

    _adopt_hf_logging(handler, json_logs=json_logs)


def _install_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    """Make ``handler`` the only handler on ``logger``, replacing any prior one."""
    logger.propagate = False
    for existing in list(logger.handlers):
        # Keep foreign handlers on ``whatdo`` (e.g. test capture); anything else
        # on third-party loggers is their default stderr handler.
        if logger.name != "whatdo" or getattr(existing, _LAYA_HANDLER_FLAG, False):
            logger.removeHandler(existing)
    logger.addHandler(handler)


def _adopt_hf_logging(handler: logging.Handler, *, json_logs: bool) -> None:
    """Route transformers / huggingface_hub logs through ``handler``.

    Both libraries install their own stderr handler when first imported, so
    they're imported here (cheap: no torch) to replace it before Laya loads.
    Their tqdm download bars bypass logging and splice ``\\r`` redraws into
    JSON lines, so they're turned off for JSON output; an explicit
    ``HF_HUB_DISABLE_PROGRESS_BARS=0`` still wins.
    """
    try:
        from huggingface_hub.utils.tqdm import (
            are_progress_bars_disabled,
            disable_progress_bars,
        )
        from transformers.utils import logging as transformers_logging
    except ImportError:  # pragma: no cover - both ship with whatdo
        return

    transformers_logging.disable_default_handler()
    for name in ("transformers", "huggingface_hub"):
        _install_handler(logging.getLogger(name), handler)

    if json_logs:
        disable_progress_bars()
        if are_progress_bars_disabled():  # False when the env var forces them on
            transformers_logging.disable_progress_bar()  # type: ignore[no-untyped-call]
