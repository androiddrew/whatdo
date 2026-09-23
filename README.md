# whatdo

A Typesafe-compatible API backed by the [Laya](https://github.com/NandhaKishorM/laya) non-autoregressive System 1 decision engine.

`whatdo` implements the **Jev API** wire contract (`POST /v1/systemone`) over the local Laya engine, so the official [`typesafe-sdk-python`](https://github.com/typesafe-ai/typesafe-sdk-python) works against a self-hosted deployment unchanged — point it at your server with `TYPESAFE_BASE_URL` and your existing `client.system_one(...)` code runs locally.

> **Status:** design complete, pre-implementation. The design is captured in `CONTEXT.md` and `docs/adr/`; the implementation is tracked as issues on the [GitHub project](https://github.com/androiddrew/whatdo/issues).

## What it does

A caller submits a **State** (the content to evaluate) and a set of **Questions**, and receives typed **Answers** in a single forward pass. Three decision primitives are supported:

- **Noul** — a calibrated boolean (probability 0–1)
- **Choice** — select one of a defined option set (returns the choice, its distribution, and a confidence)
- **Score** — rate on an ordered rubric of ≥2 levels (returns a probability-weighted value and a confidence)

### Example Curl Request

```bash
curl -X POST http://localhost:8123/v1/systemone \
  -H "Content-Type: application/json" \
  -d '{
    "model": "jev-latest",
    "state": "Hi, I have been trying to connect my Stripe account for 3 days and the integration keeps failing. This is completely blocking our checkout flow!",
    "questions": {
      "urgency_expressed": {
        "type": "noul",
        "instructions": "Does this message express high urgency or a blocked workflow?"
      }
    }
  }' | jq
```


See `CONTEXT.md` for the full domain glossary.

## Key characteristics

- **Drop-in Jev API** — `POST /v1/systemone` plus `GET /v1/models`, `/healthz`, `/readyz`.
- **Auth or no-auth** — bearer-token auth against configured API keys, or open for trusted networks.
- **Configurable inference** — one served model per deployment, a thread-based worker pool of model copies fed by a bounded queue, and a retryable `529` on overload.
- **Optional OpenTelemetry** — logs, traces, and metrics via OTLP, shipped as the `whatdo[otel]` extra (no OTEL libs required for the base install).
- **Production packaging** — an `ACCEL`-parametrized multi-stage Dockerfile (CPU + CUDA now; ROCm + Jetson planned), managed with `uv` and a committed `uv.lock`; dependencies are declared inline in `pyproject.toml` (PEP 621 extras + PEP 735 groups).
- **Configuration** via Pydantic settings (`WHATDO_`-prefixed environment variables).

## Documentation & decisions

- **Domain glossary:** [`CONTEXT.md`](./CONTEXT.md)
- **Architecture decisions:** [`docs/adr/`](./docs/adr/)
  - [0001](./docs/adr/0001-accelerator-build-matrix.md) — accelerator build matrix
  - [0002](./docs/adr/0002-packaging-dynamic-deps.md) — packaging via dynamic dependencies *(superseded by 0006)*
  - [0003](./docs/adr/0003-worker-pool-and-529-overload.md) — worker pool & 529 overload
  - [0004](./docs/adr/0004-model-resolution.md) — model resolution & the jev-latest shim
  - [0006](./docs/adr/0006-uv-project-dependencies.md) — dependencies managed by uv (pyproject + uv.lock)
- **Original brief:** [`SPECIFICATION.md`](./SPECIFICATION.md)
- **User-facing docs** (MKDocs): build locally with `make docs` (see `mkdocs.yml`) — Overview, Quickstart, Configuration, the Jev / System One contract, Deployment, Observability, and Load testing.

## Development

Developer workflow is driven by a `Makefile` (`make setup`, `lock`, `lint`, `fmt`, `typecheck`, `test`, `test-otel`, `test-slow`, `build-cpu`, `build-cuda`, `build-dev`, `docs`, `load-test`, `run`) using `uv` for environments and dependency locking. `make setup` runs `uv sync` (base deps + the `dev` group + the editable package, from `uv.lock`); `make lock` refreshes `uv.lock` and re-exports the pinned `requirements*.txt`. Tests run against a deterministic `FakeEngine` in CI (no GPU); the full end-to-end suite drives the real SDK against real Laya checkpoints on GPU-equipped machines. Load tests use [k6](https://k6.io/).

### Installing (dependencies)

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock` (ADR-0006). The Laya engine + torch are accelerator-specific extras (`cpu` / `cuda`) that pin one torch version and select the matching wheel per architecture. You do **not** have to use uv:

```bash
# uv (index selection is automatic):
uv sync --extra cpu        # or --extra cuda

# raw pip — name the torch index explicitly:
pip install "whatdo[cpu]"  --extra-index-url https://download.pytorch.org/whl/cpu
pip install "whatdo[cuda]"                     # default PyPI torch bundles cu13

# fully-pinned, reproducible, no uv — from the exported lock:
pip install -r requirements-cuda.txt                                                       # cuda: torch is on PyPI
pip install -r requirements-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu  # cpu: +cpu wheel lives on the PyTorch index
```

The exported files (`requirements.txt` base, `requirements-cpu.txt`, `requirements-cuda.txt`) are generated from `uv.lock` by `make lock` — never hand-edit them. The `cpu` file pins `torch==2.14.0+cpu`, which is published only on the PyTorch CPU index, so its install (uv or pip) must name that index; the `cuda` file's `torch==2.14.0` comes from PyPI and needs no extra index.

## Container images

One multi-stage `Dockerfile` is parametrized by an `ACCEL` build arg that selects the base image and torch wheel index (ADR-0001). `cpu` and `cuda` are implemented; `rocm`/`jetson` are documented, unbuilt slots. The builder installs the pinned deps into a uv-managed venv; the final stage copies only that venv (no dev dependencies) and runs as a non-root user.

```bash
make build-cpu     # trim CPU image (torch+cpu, no CUDA wheels), serves the real Laya engine
make build-cuda    # CUDA image (builds on CPU-only hosts; running inference needs a GPU)
make build-dev     # fast image: laya/torch skipped, FakeEngine default — for smoke tests

docker run -p 8000:8000 whatdo:cpu-dev   # then POST /v1/systemone
```

To build against a **fork of laya** (e.g. to test a patch) instead of the pinned release, pass a `git+…@ref` spec — it installs over the pinned dependency stack:

```bash
make build-cpu LAYA_FORK="git+https://github.com/you/laya@my-branch"
# or directly:
docker build --build-arg ACCEL=cpu \
  --build-arg LAYA_FORK="git+https://github.com/you/laya@my-branch" -t whatdo:cpu .
```

## Releases

Releases are tag-driven (`.github/workflows/release.yml`). Pushing a `vX.Y.Z` tag builds and pushes the **cpu** and **cuda** images to **Docker Hub** (`androiddrew/whatdo`) — each tagged `:{version}-{accel}` and `:{accel}`, and the trim cpu image additionally as `:{version}` and `:latest`.

```bash
git tag v1.2.3 && git push origin v1.2.3    # triggers the release pipeline
```

Pull a published image:

```bash
docker pull androiddrew/whatdo:1.2.3       # or :latest, :cuda
```

The release job authenticates with the `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` repository secrets (a Docker Hub access token with read/write on the `androiddrew` namespace).

## License

Apache-2.0 — see [`LICENSE`](./LICENSE). Author: Drew Bednar.
