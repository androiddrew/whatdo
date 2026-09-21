"""Wire OpenTelemetry from settings (ticket #8, ADR-0005).

Every OpenTelemetry import lives **inside** :func:`configure_observability`,
guarded by the master toggle, so importing this module — and therefore the whole
app — never requires the OTEL libraries. Providers are built locally and passed
explicitly to the instrumentation and the returned :class:`Telemetry`; nothing
is registered as a global, so a process (or a test) can build several apps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from laya_server.config import Settings
from laya_server.observability.log import configure_logging
from laya_server.observability.telemetry import Telemetry

if TYPE_CHECKING:
    from fastapi import FastAPI


def configure_observability(
    app: FastAPI,
    settings: Settings,
    *,
    span_exporter: Any = None,
    metric_reader: Any = None,
) -> Telemetry:
    """Configure logging + OTEL for ``app`` and return its :class:`Telemetry`.

    When ``otel.enabled`` is false, only JSON logging is configured and a no-op
    ``Telemetry`` is returned — the request path then records into nothing.
    ``span_exporter`` / ``metric_reader`` are test seams for in-memory exporters;
    production uses OTLP exporters pointed at ``otel.endpoint``.
    """
    otel = settings.otel
    if not otel.enabled:
        configure_logging(
            level=settings.logging.level, json_logs=settings.logging.json_logs
        )
        return Telemetry()

    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": otel.service_name})
    tracer = _configure_traces(app, settings, resource, span_exporter)
    instruments = _configure_metrics(app, settings, resource, metric_reader)

    # The logs signal (independent of traces) adds trace/span ids to each log;
    # with traces off there is no active span, so no ids are added.
    trace_context = _trace_context_provider() if otel.logs else None
    configure_logging(
        level=settings.logging.level,
        json_logs=settings.logging.json_logs,
        trace_context=trace_context,
    )
    return Telemetry(tracer=tracer, **instruments)


def _configure_traces(
    app: FastAPI, settings: Settings, resource: Any, span_exporter: Any
) -> Any:
    if not settings.otel.traces:
        return None
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider(resource=resource)
    exporter = (
        span_exporter if span_exporter is not None else _otlp_span_exporter(settings)
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    # Held on the app so the provider (and its processor) outlives this call.
    app.state.otel_tracer_provider = provider
    return provider.get_tracer("laya_server")


def _configure_metrics(
    app: FastAPI, settings: Settings, resource: Any, metric_reader: Any
) -> dict[str, Any]:
    if not settings.otel.metrics:
        return {}
    from opentelemetry.metrics import CallbackOptions, Observation
    from opentelemetry.sdk.metrics import MeterProvider

    reader = (
        metric_reader if metric_reader is not None else _otlp_metric_reader(settings)
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    meter = provider.get_meter("laya_server")

    pool = app.state.pool

    def _observe_queue_depth(_options: CallbackOptions) -> list[Observation]:
        return [Observation(pool.queue_depth())]

    meter.create_observable_gauge(
        "laya.queue.depth",
        callbacks=[_observe_queue_depth],
        description="Requests waiting in the shared inference queue.",
    )
    app.state.otel_meter_provider = provider
    return {
        "requests": meter.create_counter(
            "laya.requests", description="System One requests accepted."
        ),
        "requests_by_model": meter.create_counter(
            "laya.requests.by_model",
            description="System One requests per resolved model.",
        ),
        "inference_duration": meter.create_histogram(
            "laya.inference.duration", unit="s", description="Inference latency."
        ),
        "questions_per_request": meter.create_histogram(
            "laya.request.questions", description="Questions per System One request."
        ),
        "overloads": meter.create_counter(
            "laya.overloads", description="Requests shed as overload (529)."
        ),
    }


def _otlp_span_exporter(settings: Settings) -> Any:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    # endpoint=None is the exporter's default (falls back to env/localhost).
    return OTLPSpanExporter(endpoint=settings.otel.endpoint)


def _otlp_metric_reader(settings: Settings) -> Any:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    return PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel.endpoint)
    )


def shutdown_observability(app: FastAPI) -> None:
    """Flush and stop any OTEL providers built for ``app`` (called on shutdown).

    A no-op when observability is off. Without this the metric reader's periodic
    export thread would leak and buffered spans/metrics would be lost.
    """
    for attr in ("otel_tracer_provider", "otel_meter_provider"):
        provider = getattr(app.state, attr, None)
        if provider is not None:
            provider.shutdown()


def _trace_context_provider() -> Any:
    from opentelemetry import trace

    def provider() -> dict[str, str] | None:
        span = trace.get_current_span()
        context = span.get_span_context()
        if not context.is_valid:
            return None
        return {
            "trace_id": trace.format_trace_id(context.trace_id),
            "span_id": trace.format_span_id(context.span_id),
        }

    return provider
