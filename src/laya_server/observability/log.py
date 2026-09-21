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
    """Install a single handler on the ``laya_server`` logger (idempotent).

    Uses a dedicated logger (not root) so repeated app builds in tests don't
    stack handlers and pytest's own logging is left alone. This mutates a
    process-global logger, so building two apps with different logging settings
    in one process is last-writer-wins — fine for the single-app deployment.
    """
    logger = logging.getLogger("laya_server")
    logger.setLevel(level.upper())
    logger.propagate = False

    # Drop any handler we installed on a previous build before adding a fresh one.
    for existing in list(logger.handlers):
        if getattr(existing, _LAYA_HANDLER_FLAG, False):
            logger.removeHandler(existing)

    handler = logging.StreamHandler()
    setattr(handler, _LAYA_HANDLER_FLAG, True)
    if json_logs:
        handler.setFormatter(JsonFormatter(trace_context=trace_context))
    logger.addHandler(handler)
