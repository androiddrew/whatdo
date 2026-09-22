# Observability

OpenTelemetry support is **optional and off by default**. The OTEL libraries live
in the `whatdo[otel]` extra; the base install imports and runs without them.
Enable it with the master toggle, and control each signal independently.

```bash
pip install "whatdo[otel]"

WHATDO_OTEL__ENABLED=true
WHATDO_OTEL__TRACES=true
WHATDO_OTEL__METRICS=true
WHATDO_OTEL__LOGS=true
WHATDO_OTEL__ENDPOINT=http://otel-collector:4317   # OTLP endpoint
WHATDO_OTEL__SERVICE_NAME=whatdo
```

When disabled, the request path records into a no-op telemetry facade — it costs
nothing on the hot path.

## Traces

FastAPI auto-instrumentation records a server span per request, and each System
One call adds a child span (`inference`) around the engine forward pass, tagged
with the resolved **Model** and the number of **Questions**.

## Metrics

Six custom instruments are exported:

| Metric | Kind | Meaning |
| ------ | ---- | ------- |
| `laya.requests` | counter | System One requests served. |
| `laya.requests.by_model` | counter | Requests served, dimensioned by resolved **Model**. |
| `laya.inference.duration` | histogram (s) | Engine forward-pass latency. |
| `laya.request.questions` | histogram | **Questions** per request. |
| `laya.queue.depth` | observable gauge | Requests waiting in the shared worker-pool queue. |
| `laya.overloads` | counter | Requests shed as overload (`529`). |

## Logs

Logs are structured JSON. When the logs signal is on and a span is active, each
record is correlated with the current trace via `trace_id` / `span_id`.

## Testing it

The emission behaviour is covered by tests using in-memory exporters, so enabling
OTEL is verified end-to-end (spans and metrics) without a running collector.
