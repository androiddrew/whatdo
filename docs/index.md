# laya-server

`laya-server` is a FastAPI service that speaks TypeSafe's **Jev API** contract
(`POST /v1/systemone`) over the local **Laya** decision engine, so the official
[`typesafe-sdk-python`](https://github.com/typesafe-ai/typesafe-sdk-python) can
drive locally-served, non-autoregressive typed decisions unchanged — point it at
your deployment with `TYPESAFE_BASE_URL` and your existing `client.system_one(...)`
code runs against it.

## What it does

A caller submits a **State** — the content under evaluation — and a set of
**Questions**, and receives typed **Answers** in a single **System One** call
(one forward pass). Exactly three **Question** types exist:

- **Noul** — a calibrated boolean, returned as a probability from 0 to 1.
- **Choice** — selects one option from a defined set, returning the chosen
  option, the full probability distribution, and a **Confidence**.
- **Score** — rates the State on an ordered rubric of at least two levels,
  returning a probability-weighted value and a **Confidence**.

What a **Question** is judged against — a Choice's option set or a Score's rubric
levels — is its **Criteria**.

## Key characteristics

- **Drop-in Jev API** — `POST /v1/systemone` plus `GET /v1/models`, and the
  `/healthz` / `/readyz` probes.
- **One Served Model per deployment**, resolved from the requested **Model** id,
  with an always-on `jev-latest` / `jev-preview` compatibility shim.
- **Auth or no-auth** — bearer-token auth against configured API keys, or open
  for trusted networks.
- **Throughput and backpressure** — a thread worker pool of engine copies fed by
  a bounded queue, with a retryable `529` on overload.
- **Optional OpenTelemetry** — traces, metrics, and structured logs, shipped as
  the `laya-server[otel]` extra (no OTEL libraries in the base install).

!!! note "`usage.output_tokens` is always 0 — on purpose"
    Every response reports **Usage**, which carries `input_tokens`. Its
    `output_tokens` is **always `0`**: Laya is non-autoregressive and generates
    no tokens, so there is nothing to count. This is a deliberate contract quirk,
    not a bug — see the [Jev / System One contract](contract.md).

## Where to next

- [Quickstart](quickstart.md) — run the server and drive it with the official SDK.
- [Configuration](configuration.md) — every `LAYA_` setting.
- [Jev / System One contract](contract.md) — the request/response wire shape.
- [Deployment](deployment.md) — the CPU and CUDA container images.
- [Observability](observability.md) — optional OpenTelemetry.
- [Load testing](load-testing.md) — driving the server with k6.
