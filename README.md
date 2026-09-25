# whatdo

A Typesafe-compatible API backed by the [Laya](https://github.com/NandhaKishorM/laya) non-autoregressive System 1 decision engine.

`whatdo` implements the **Jev API** wire contract (`POST /v1/systemone`) over the local Laya engine, so the official [`typesafe-sdk-python`](https://github.com/typesafe-ai/typesafe-sdk-python) works against a self-hosted deployment unchanged — point it at your server with `TYPESAFE_BASE_URL` and your existing `client.system_one(...)` code runs locally.

## What it does

A caller submits a **State** (the content to evaluate) and a set of **Questions**, and receives typed **Answers** in a single forward pass. Three decision primitives are supported:

- **Noul** — a calibrated boolean (probability 0–1)
- **Choice** — select one of a defined option set (returns the choice, its distribution, and a confidence)
- **Score** — rate on an ordered rubric of ≥2 levels (returns a probability-weighted value and a confidence)

### Key characteristics

- **Drop-in Jev API** — `POST /v1/systemone` plus `GET /v1/models`, `/healthz`, `/readyz`.
- **Auth or no-auth** — bearer-token auth against configured API keys, or open for trusted networks.
- **Configurable inference** — one served model per deployment, a thread-based worker pool of model copies fed by a bounded queue, and a retryable `529` on overload.
- **Optional OpenTelemetry** — logs, traces, and metrics via OTLP, shipped as the `whatdo[otel]` extra (no OTEL libs required for the base install).
- **Production packaging** — an `ACCEL`-parametrized multi-stage Dockerfile (CPU + CUDA now; ROCm + Jetson planned), managed with `uv` and a committed `uv.lock`; dependencies are declared inline in `pyproject.toml` (PEP 621 extras + PEP 735 groups).
- **Configuration** via Pydantic settings (`WHATDO_`-prefixed environment variables).

## Installation

whatdo requires Python >= 3.12. Every install includes the Laya engine and PyTorch; the choice below is only which PyTorch build you get.

### From PyPI

Create a virtual environment first (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Nvidia CUDA**

```bash
pip install whatdo
```

**CPU**:

```bash
pip install whatdo --extra-index-url https://download.pytorch.org/whl/cpu
```

**macOS** (uses the Apple GPU when available, otherwise the CPU):

```bash
pip install whatdo
```

### From the GitHub source

Clone the repository:

```bash
git clone https://github.com/androiddrew/whatdo.git
cd whatdo
```

**With [uv](https://docs.astral.sh/uv/)** (creates `.venv` and installs the exact locked versions):

```bash
uv sync --extra cuda    # CUDA (Linux with an NVIDIA GPU)
uv sync --extra cpu     # CPU (Linux without a GPU, or macOS)
source .venv/bin/activate
```

**With pip** (installs the exact locked versions from the `requirements-*.txt` files, then whatdo itself from the checkout):

CUDA:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-cuda.txt
pip install --no-deps .
```

CPU (Linux without a GPU, or macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
pip install --no-deps .
```

The requirements files pin every dependency but not whatdo itself; `pip install --no-deps .` installs whatdo from the checkout without changing those pinned versions.

## Starting the Server

### Example Curl Requests

```bash
curl -X POST http://localhost:8000/v1/systemone \
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

```bash
curl -X POST http://localhost:8000/v1/systemone \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
  "model": "jev-latest",
  "state": "Help! I was charged twice for my subscription this month and I need a refund immediately before my account overdrafts.",
  "questions": {
    "urgency": {
      "type": "noul",
      "instructions": "Does this message express urgency or request immediate action?"
    },
    "routing_department": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {
        "billing": ["charges", "invoices", "refunds"],
        "technical": ["bugs", "outages", "errors"],
        "general": null
      }
    },
    "severity": {
      "type": "score",
      "instructions": "How severe is the issue?",
      "criteria": [
        "Cosmetic or informational",
        "Workaround exists, non-critical",
        "Blocking issue, requires immediate intervention"
      ]
    }
  }
}' | jq
```

## Design

The domain glossary lives in [`CONTEXT.md`](https://github.com/androiddrew/whatdo/blob/main/CONTEXT.md), and the architecture decisions in [`docs/adr/`](https://github.com/androiddrew/whatdo/tree/main/docs/adr).

## Development

Developer workflow is driven by a `Makefile` (`make setup`, `lock`, `lint`, `fmt`, `typecheck`, `test`, `test-otel`, `test-slow`, `build-cpu`, `build-cuda`, `docs`, `load-test`, `run`) using `uv` for environments and dependency locking. `make setup` runs `uv sync --extra cpu` (base deps incl. Laya + the CPU torch build, the `dev` group, and the editable package, from `uv.lock`; use `make setup ACCEL=cuda` on a GPU box); `make lock` refreshes `uv.lock` and re-exports the pinned `requirements*.txt`. Tests run against a deterministic `FakeEngine` in CI (no GPU); the full end-to-end suite drives the real SDK against real Laya checkpoints on GPU-equipped machines. Load tests use [k6](https://k6.io/).

## Container images

One multi-stage `Dockerfile` is parametrized by an `ACCEL` build arg that selects the base image and torch wheel index (ADR-0001). `cpu` and `cuda` are implemented; `rocm`/`jetson` are documented, unbuilt slots. The builder installs the pinned deps into a uv-managed venv; the final stage copies only that venv (no dev dependencies) and runs as a non-root user.

```bash
make build-cpu     # trim CPU image (torch+cpu, no CUDA wheels), serves the real Laya engine
make build-cuda    # CUDA image (builds on CPU-only hosts; running inference needs a GPU)

docker run -p 8000:8000 whatdo:cpu-dev   # then POST /v1/systemone
```

To build against a **fork of laya** (e.g. to test a patch) instead of the pinned release, pass a `git+…@ref` spec — it installs over the pinned dependency stack:

```bash
make build-cpu LAYA_FORK="git+https://github.com/you/laya@my-branch"
# or directly:
docker build --build-arg ACCEL=cpu \
  --build-arg LAYA_FORK="git+https://github.com/you/laya@my-branch" -t whatdo:cpu .
```

## License

Apache-2.0 — see [`LICENSE`](./LICENSE). Author: Drew Bednar.
