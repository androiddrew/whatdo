"""Structured JSON logging and trace correlation (#8).

The formatter unit tests need no OTEL; the correlation test exercises the real
trace-context provider and is skipped in the base install.
"""

from __future__ import annotations

import json
import logging

import pytest

from whatdo.observability.log import JsonFormatter


def _record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="whatdo.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_emits_structured_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record("boom")))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "whatdo.test"
    assert payload["message"] == "boom"
    assert "trace_id" not in payload  # no provider => no correlation


def test_json_formatter_merges_trace_context_when_provided() -> None:
    formatter = JsonFormatter(
        trace_context=lambda: {"trace_id": "abc", "span_id": "def"}
    )
    payload = json.loads(formatter.format(_record()))
    assert payload["trace_id"] == "abc"
    assert payload["span_id"] == "def"


def test_trace_context_provider_reads_the_active_span() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider

    from whatdo.observability.setup import _trace_context_provider

    provider = _trace_context_provider()
    # No active span yet.
    assert provider() is None

    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("unit"):
        context = provider()
    assert context is not None
    assert len(context["trace_id"]) == 32  # 128-bit id, hex
    assert len(context["span_id"]) == 16
