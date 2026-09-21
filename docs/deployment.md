# Deployment

`laya-server` ships as one multi-stage `Dockerfile` parametrized by an `ACCEL`
build arg that selects the base image and torch wheel index. `cpu` and `cuda`
are implemented; `rocm` and `jetson` exist as documented, unbuilt slots.

## Build

```bash
make build-cpu     # trim CPU image (torch+cpu, no CUDA wheels)
make build-cuda    # CUDA image (builds on CPU-only hosts; running needs a GPU)
make build-dev     # fast image: laya/torch skipped, FakeEngine default
```

The builder installs the pinned requirements into a `uv`-managed virtualenv; the
final stage copies only that interpreter + venv (no dev dependencies) and runs as
a non-root user. The CPU image is genuinely trim — it installs `torch+cpu` and
carries no CUDA wheels.

!!! note "Image size"
    Only the CPU image is "trim" (hundreds of MB). The CUDA image is necessarily
    large — multi-GB torch/CUDA wheels — which is expected for the accelerator
    variant.

### Installing Laya from a fork

To build against a fork of the `laya` package (for example to test a patch)
instead of the pinned release, pass a `git+…@ref` spec; it installs over the
pinned dependency stack:

```bash
make build-cpu LAYA_FORK="git+https://github.com/you/laya@my-branch"
```

## Run

```bash
docker run -p 8000:8000 \
  -e LAYA_MODEL__ENGINE=laya \
  git.runcible.io/androiddrew/laya-server:latest
```

The real Laya engine loads a **Checkpoint** at startup; `/readyz` returns
`503` until it is loaded and `200` once the deployment is ready to serve. Use
`/healthz` for liveness (it does not depend on the model).

### GPU

Run the CUDA image with the NVIDIA container runtime so the container can see the
GPU:

```bash
docker run --gpus all -p 8000:8000 \
  git.runcible.io/androiddrew/laya-server:cuda
```

## Configuration & probes

- Configure via `LAYA_`-prefixed environment variables — see
  [Configuration](configuration.md).
- **Liveness:** `GET /healthz` → `200 {"status":"ok"}` while the process is up.
- **Readiness:** `GET /readyz` → `200 {"status":"ready"}` once every engine copy
  in the worker pool has loaded; `503` otherwise. Gate traffic on readiness.

## Scaling

A deployment serves a single **Served Model** with a worker pool of `pool_size`
copies fed by one bounded queue (`queue_max`); when the queue saturates, requests
get a retryable `529`. Scale horizontally by running more container replicas.
