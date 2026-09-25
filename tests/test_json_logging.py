"""Structured JSON logging and trace correlation (#8).

The formatter unit tests need no OTEL; the correlation test exercises the real
trace-context provider and is skipped in the base install.
"""

from __future__ import annotations

import json
import logging

import pytest

from whatdo.observability.log import (
    _LAYA_HANDLER_FLAG,
    JsonFormatter,
    configure_logging,
)


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
    assert payload["thread"] == "MainThread"
    assert "trace_id" not in payload  # no provider => no correlation


def test_json_formatter_merges_trace_context_when_provided() -> None:
    formatter = JsonFormatter(
        trace_context=lambda: {"trace_id": "abc", "span_id": "def"}
    )
    payload = json.loads(formatter.format(_record()))
    assert payload["trace_id"] == "abc"
    assert payload["span_id"] == "def"


def test_plain_logs_use_a_readable_text_format() -> None:
    configure_logging(level="INFO", json_logs=False)
    try:
        (handler,) = [
            h
            for h in logging.getLogger("whatdo").handlers
            if getattr(h, _LAYA_HANDLER_FLAG, False)
        ]
        line = handler.format(_record("boom"))
        assert "INFO" in line
        assert "whatdo.test" in line
        assert "[MainThread]" in line
        assert line.endswith("boom")
    finally:
        configure_logging(level="INFO", json_logs=True)


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


def _our_handlers(name: str) -> list[logging.Handler]:
    return [
        h
        for h in logging.getLogger(name).handlers
        if getattr(h, _LAYA_HANDLER_FLAG, False)
    ]


@pytest.mark.parametrize("name", ["uvicorn", "transformers", "huggingface_hub"])
def test_third_party_loggers_share_the_whatdo_handler(name: str) -> None:
    configure_logging(level="INFO", json_logs=True)

    logger = logging.getLogger(name)
    # Exactly our handler: the library's own stderr handler is gone, and a
    # rebuild replaces rather than stacks it.
    configure_logging(level="INFO", json_logs=True)
    assert logger.handlers == _our_handlers("whatdo")
    assert logger.propagate is False


def test_uvicorn_children_propagate_to_the_shared_handler() -> None:
    # As if uvicorn's own dictConfig ran first (``uvicorn whatdo.app:app``).
    access = logging.getLogger("uvicorn.access")
    access.addHandler(logging.StreamHandler())
    access.propagate = False

    configure_logging(level="INFO", json_logs=True)

    for name in ("uvicorn.error", "uvicorn.access"):
        child = logging.getLogger(name)
        assert child.handlers == []
        assert child.propagate is True


def test_json_logs_disable_hf_progress_bars() -> None:
    from huggingface_hub.utils import are_progress_bars_disabled, enable_progress_bars
    from transformers.utils import logging as transformers_logging

    try:
        configure_logging(level="INFO", json_logs=True)
        assert are_progress_bars_disabled()
        assert not transformers_logging.is_progress_bar_enabled()
    finally:
        enable_progress_bars()
        transformers_logging.enable_progress_bar()
