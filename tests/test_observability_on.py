"""With observability on, the server emits the expected spans and metrics (#8).

Skipped in the base install; where ``whatdo[otel]`` is present it drives a
request through an in-memory exporter/reader and asserts what was emitted.
"""

from __future__ import annotations

import threading

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from tests.conftest import BlockingEngine, serve  # noqa: E402
from whatdo.app import create_app  # noqa: E402
from whatdo.config import OtelSettings, ServerSettings, Settings  # noqa: E402
from whatdo.inference.fake import FakeEngine  # noqa: E402

_BODY = {
    "state": "I was charged twice.",
    "model": "jev-latest",
    "questions": {
        "billing": {"type": "noul", "instructions": "billing?"},
        "tone": {"type": "choice", "criteria": {"calm": None, "angry": None}},
    },
}


def _otel_app(
    settings: Settings, engine: object
) -> tuple[FastAPI, InMemorySpanExporter, InMemoryMetricReader]:
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    app = create_app(
        settings=settings,
        engine=engine,  # type: ignore[arg-type]
        otel_span_exporter=span_exporter,
        otel_metric_reader=metric_reader,
    )
    return app, span_exporter, metric_reader


def _metric_names(reader: InMemoryMetricReader) -> set[str]:
    data = reader.get_metrics_data()
    names: set[str] = set()
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                names.add(metric.name)
    return names


def test_request_emits_server_and_inference_spans() -> None:
    settings = Settings(otel=OtelSettings(enabled=True, endpoint=None))
    app, spans, _ = _otel_app(settings, FakeEngine())
    with TestClient(app) as client:
        assert client.post("/v1/systemone", json=_BODY).status_code == 200

    names = [span.name for span in spans.get_finished_spans()]
    assert "inference" in names  # our custom span
    # FastAPI auto-instrumentation records a server span for the route.
    assert any("/v1/systemone" in name for name in names)


def test_request_records_the_custom_metrics() -> None:
    settings = Settings(otel=OtelSettings(enabled=True, endpoint=None))
    app, _, reader = _otel_app(settings, FakeEngine())
    with TestClient(app) as client:
        assert client.post("/v1/systemone", json=_BODY).status_code == 200

    names = _metric_names(reader)
    assert {
        "laya.requests",
        "laya.requests.by_model",
        "laya.inference.duration",
        "laya.request.questions",
        "laya.queue.depth",
    } <= names


def test_traces_on_metrics_off_emits_spans_but_no_meter() -> None:
    settings = Settings(
        otel=OtelSettings(enabled=True, traces=True, metrics=False, endpoint=None)
    )
    app, spans, _ = _otel_app(settings, FakeEngine())
    with TestClient(app) as client:
        assert client.post("/v1/systemone", json=_BODY).status_code == 200

    assert "inference" in [span.name for span in spans.get_finished_spans()]
    # Metrics off: no meter provider built.
    assert not hasattr(app.state, "otel_meter_provider")
    assert hasattr(app.state, "otel_tracer_provider")


def test_metrics_on_traces_off_records_metrics_but_no_span() -> None:
    settings = Settings(
        otel=OtelSettings(enabled=True, traces=False, metrics=True, endpoint=None)
    )
    app, spans, reader = _otel_app(settings, FakeEngine())
    with TestClient(app) as client:
        assert client.post("/v1/systemone", json=_BODY).status_code == 200

    assert spans.get_finished_spans() == ()  # traces off: nothing exported
    assert not hasattr(app.state, "otel_tracer_provider")
    assert "laya.requests" in _metric_names(reader)


def test_shutdown_observability_stops_providers_and_is_idempotent() -> None:
    from whatdo.observability import shutdown_observability

    settings = Settings(otel=OtelSettings(enabled=True, endpoint=None))
    app, _, _ = _otel_app(settings, FakeEngine())
    with TestClient(app):
        pass  # lifespan enter/exit already calls shutdown once
    # Safe to call again: shutdown is idempotent.
    shutdown_observability(app)


def test_overload_increments_the_overload_counter() -> None:
    engine = BlockingEngine()
    settings = Settings(
        otel=OtelSettings(enabled=True, endpoint=None),
        server=ServerSettings(queue_max=1, request_timeout=30.0),
    )
    app, _, reader = _otel_app(settings, engine)

    with serve(app) as base_url:
        statuses: list[int] = []
        lock = threading.Lock()

        def call() -> None:
            status = httpx.post(
                f"{base_url}/v1/systemone", json=_BODY, timeout=15
            ).status_code
            with lock:
                statuses.append(status)

        pinner = threading.Thread(target=call)
        pinner.start()
        assert engine.entered.wait(timeout=5)
        extras = [threading.Thread(target=call) for _ in range(3)]
        for thread in extras:
            thread.start()
        for thread in extras:
            thread.join(timeout=10)
        engine.release()
        pinner.join(timeout=10)

    assert 529 in statuses
    assert "laya.overloads" in _metric_names(reader)
