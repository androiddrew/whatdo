# laya-server

A Typesafe-compatible API backed by the [Laya](https://github.com/NandhaKishorM/laya) non-autoregressive System 1 decision engine.

`laya-server` implements the **Jev API** wire contract (`POST /v1/systemone`) over the local Laya engine, so the official [`typesafe-sdk-python`](https://github.com/typesafe-ai/typesafe-sdk-python) works against a self-hosted deployment unchanged — point it at your server with `TYPESAFE_BASE_URL` and your existing `client.system_one(...)` code runs locally.

> **Status:** design complete, pre-implementation. The design is captured in `CONTEXT.md` and `docs/adr/`; the implementation is tracked as issues on the [Gitea project](https://git.runcible.io/androiddrew/laya-server/issues).

## What it does

A caller submits a **State** (the content to evaluate) and a set of **Questions**, and receives typed **Answers** in a single forward pass. Three decision primitives are supported:

- **Noul** — a calibrated boolean (probability 0–1)
- **Choice** — select one of a defined option set (returns the choice, its distribution, and a confidence)
- **Score** — rate on an ordered rubric of ≥2 levels (returns a probability-weighted value and a confidence)

See `CONTEXT.md` for the full domain glossary.

## Key characteristics

- **Drop-in Jev API** — `POST /v1/systemone` plus `GET /v1/models`, `/healthz`, `/readyz`.
- **Auth or no-auth** — bearer-token auth against configured API keys, or open for trusted networks.
- **Configurable inference** — one served model per deployment, a thread-based worker pool of model copies fed by a bounded queue, and a retryable `529` on overload.
- **Optional OpenTelemetry** — logs, traces, and metrics via OTLP, shipped as the `laya-server[otel]` extra (no OTEL libs required for the base install).
- **Production packaging** — an `ACCEL`-parametrized multi-stage Dockerfile (CPU + CUDA now; ROCm + Jetson planned), managed with `uv` and pinned requirements files.
- **Configuration** via Pydantic settings (`LAYA_`-prefixed environment variables).

## Documentation & decisions

- **Domain glossary:** [`CONTEXT.md`](./CONTEXT.md)
- **Architecture decisions:** [`docs/adr/`](./docs/adr/)
  - [0001](./docs/adr/0001-accelerator-build-matrix.md) — accelerator build matrix
  - [0002](./docs/adr/0002-packaging-dynamic-deps.md) — packaging via dynamic dependencies
  - [0003](./docs/adr/0003-worker-pool-and-529-overload.md) — worker pool & 529 overload
  - [0004](./docs/adr/0004-model-resolution.md) — model resolution & the jev-latest shim
- **Original brief:** [`SPECIFICATION.md`](./SPECIFICATION.md)
- **Full user-facing docs** (MKDocs) are planned — see the deployment/observability/quickstart chapters tracked in the issues.

## Development

Developer workflow is driven by a `Makefile` (`make setup`, `lint`, `fmt`, `typecheck`, `test`, `test-slow`, `build-cpu`, `build-cuda`, `build-dev`, `docs`, `load-test`, `run`) using `uv` for environments and dependency compilation. Tests run against a deterministic `FakeEngine` in CI (no GPU); the full end-to-end suite drives the real SDK against real Laya checkpoints on GPU-equipped machines. Load tests use [k6](https://k6.io/).

## Container images

One multi-stage `Dockerfile` is parametrized by an `ACCEL` build arg that selects the base image and torch wheel index (ADR-0001). `cpu` and `cuda` are implemented; `rocm`/`jetson` are documented, unbuilt slots. The builder installs the pinned deps into a uv-managed venv; the final stage copies only that venv (no dev dependencies) and runs as a non-root user.

```bash
make build-cpu     # trim CPU image (torch+cpu, no CUDA wheels), serves the real Laya engine
make build-cuda    # CUDA image (builds on CPU-only hosts; running inference needs a GPU)
make build-dev     # fast image: laya/torch skipped, FakeEngine default — for smoke tests

docker run -p 8000:8000 laya-server:cpu-dev   # then POST /v1/systemone
```

To build against a **fork of laya** (e.g. to test a patch) instead of the pinned release, pass a `git+…@ref` spec — it installs over the pinned dependency stack:

```bash
make build-cpu LAYA_FORK="git+https://github.com/you/laya@my-branch"
# or directly:
docker build --build-arg ACCEL=cpu \
  --build-arg LAYA_FORK="git+https://github.com/you/laya@my-branch" -t laya-server:cpu .
```

## License

Apache-2.0 — see [`LICENSE`](./LICENSE). Author: Drew Bednar.
