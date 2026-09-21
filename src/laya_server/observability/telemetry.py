"""The telemetry facade the request path records through (ticket #8).

Deliberately imports **no** OpenTelemetry: it holds already-built instrument and
tracer handles (or ``None``) injected by :mod:`laya_server.observability.setup`,
so the base install — which has no OTEL libraries — imports this module fine. A
``Telemetry()`` with every handle ``None`` is the no-op used when observability
(or an individual signal) is disabled, and it costs nothing on the hot path.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class Telemetry:
    """Records the service's custom metrics and inference spans.

    Each handle is optional so a partially-enabled configuration (e.g. traces on,
    metrics off) simply skips the signals it lacks. The handles are OTEL
    instrument/tracer objects, typed ``Any`` here to keep this module import-free
    of OpenTelemetry.
    """

    def __init__(
        self,
        *,
        tracer: Any = None,
        requests: Any = None,
        requests_by_model: Any = None,
        inference_duration: Any = None,
        questions_per_request: Any = None,
        overloads: Any = None,
    ) -> None:
        self._tracer = tracer
        self._requests = requests
        self._requests_by_model = requests_by_model
        self._inference_duration = inference_duration
        self._questions_per_request = questions_per_request
        self._overloads = overloads

    def record_request(self, *, model: str, question_count: int) -> None:
        """Count one accepted System One request (total, per-model, question count)."""
        if self._requests is not None:
            self._requests.add(1)
        if self._requests_by_model is not None:
            self._requests_by_model.add(1, {"laya.model": model})
        if self._questions_per_request is not None:
            self._questions_per_request.record(question_count)

    def record_inference_latency(self, seconds: float) -> None:
        """Record the wall-clock latency of a completed inference, in seconds."""
        if self._inference_duration is not None:
            self._inference_duration.record(seconds)

    def record_overload(self) -> None:
        """Count one request shed as overload (529)."""
        if self._overloads is not None:
            self._overloads.add(1)

    @contextmanager
    def inference_span(self, *, model: str, question_count: int) -> Iterator[Any]:
        """A span around the inference call; a no-op when tracing is off."""
        if self._tracer is None:
            yield None
            return
        with self._tracer.start_as_current_span(
            "inference",
            attributes={"laya.model": model, "laya.question_count": question_count},
        ) as span:
            yield span
