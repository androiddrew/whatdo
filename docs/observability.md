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

Application logs go to the `whatdo` logger, configured by `WHATDO_LOGGING__LEVEL`
(default `INFO`) and `WHATDO_LOGGING__JSON_LOGS` (default `true`). Uvicorn's
`--log-level` only affects uvicorn's own access/server lines, not these. The
`whatdo serve --log-level` flag sets both.

Uvicorn's server and access lines, and any `transformers` / `huggingface_hub`
warnings, go through the same handler, so every line shares one format. With
JSON logs on, Hugging Face's download progress bars are turned off because they
write straight to stderr and break up JSON lines. Set
`HF_HUB_DISABLE_PROGRESS_BARS=0` to keep them anyway.

JSON records carry `timestamp`, `level`, `logger`, `thread` and `message`. When
the OTEL logs signal is on and a span is active, each record is also correlated
with the current trace via `trace_id` / `span_id`. With `JSON_LOGS=false` the
same records are rendered as plain text for local development.

| Level | What is logged |
| ----- | -------------- |
| `INFO` | Startup summary (engine, served model, worker count, queue/timeout, auth and OTEL state), one line per worker describing its engine copy, each engine's load (including Laya's resolved device and dtype), pool readiness, shutdown, and requests rejected for an unserved **Model**. |
| `WARNING` | Requests shed as overload (queue full) or timed out (`529`). |
| `ERROR` | An engine that failed to load, with its traceback. |
| `DEBUG` | Per request: model resolution, queue depth, the questions sent to the engine, answers, token counts and latencies. |

The `thread` field (`laya-worker-N`) shows which engine copy handled a record.
**State** payloads are never logged, since they may carry user data; API keys
are never logged either.

For local development:

```bash
WHATDO_LOGGING__JSON_LOGS=false WHATDO_LOGGING__LEVEL=DEBUG make run
```

## Testing it

The emission behaviour is covered by tests using in-memory exporters, so enabling
OTEL is verified end-to-end (spans and metrics) without a running collector.
