# Optional OpenTelemetry observability, off by default

Observability is opt-in and costs nothing when off. The OpenTelemetry libraries live in the `laya-server[otel]` extra (ADR-0002), and **every OTEL import is guarded** inside `configure_observability`, behind the `LAYA_OTEL__ENABLED` master toggle — so the base install imports and runs without them. A master toggle plus independent per-signal toggles (`traces`/`metrics`/`logs`) and a configurable OTLP endpoint + service name all live in `Settings`. When disabled, the request path records into a no-op `Telemetry` facade that holds no instruments.

Traces come from FastAPI auto-instrumentation plus a custom `inference` span around the worker-pool call. Metrics are six custom instruments — request count, per-`Model` counter, inference-latency histogram, questions-per-request histogram, an observable queue-depth gauge read off the pool, and a 529-overload counter. Logs are structured JSON, correlated with the active span's trace/span ids when tracing is on.

Provider setup builds `TracerProvider`/`MeterProvider` **locally and passes them explicitly** to instrumentation and to the `Telemetry` object; nothing is registered as an OTEL global. This keeps a process (and the test suite) free to build several apps, and lets tests inject in-memory exporters/readers through the app factory.

## Consequences

- The emission tests are `importorskip`-gated: they run only where the `[otel]` extra is installed. CI runs them in a dedicated `test-otel` job; the base `test` job proves the OTEL-off path.
- No OTEL global providers means third-party libraries that read the global tracer won't see ours; acceptable, since all our spans/metrics flow through the explicitly-wired providers.
