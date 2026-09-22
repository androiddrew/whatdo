# syntax=docker/dockerfile:1
#
# One multi-stage image parametrized by ACCEL (ADR-0001): ACCEL selects both the
# base image (below) and the torch wheel index (in the builder). `cpu` and `cuda`
# are built in CI; `rocm` and `jetson` are documented, unbuilt slots.
#
#   docker build --build-arg ACCEL=cpu  -t whatdo:cpu  .
#   docker build --build-arg ACCEL=cuda -t whatdo:cuda .
#
# Install laya from a fork instead of the pinned release (e.g. to test a patch):
#   docker build --build-arg LAYA_FORK="git+https://github.com/you/laya@my-branch" .

ARG ACCEL=cpu

# --------------------------------------------------------------------------- #
# Accelerator base images. `FROM base-${ACCEL}` below resolves to one of these
# purely from the build arg — no per-target Dockerfiles to drift (ADR-0001).
# --------------------------------------------------------------------------- #
FROM ubuntu:24.04 AS base-cpu
# CUDA 13 to match the cu13 torch stack pinned in laya-requirements.txt.
FROM nvidia/cuda:13.0.1-runtime-ubuntu24.04 AS base-cuda
# Unbuilt slots — uncomment and validate once we have the hardware:
# FROM rocm/dev-ubuntu-24.04:6.2 AS base-rocm
# FROM nvcr.io/nvidia/l4t-jetpack:r36.3.0 AS base-jetson

# --------------------------------------------------------------------------- #
# Builder: uv-managed Python + venv with the pinned deps and the laya engine.
# --------------------------------------------------------------------------- #
FROM base-${ACCEL} AS builder
ARG ACCEL

# uv installs Python here (not the venv) so the final stage can copy both the
# venv and its interpreter and keep the symlinks valid.
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH \
    DEBIAN_FRONTEND=noninteractive

# git is needed for the optional laya-from-fork (git+) install; curl to fetch uv.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

# Pinned uv, then a uv-managed CPython and an empty venv.
COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /uvx /root/.local/bin/
RUN uv python install 3.12 \
    && uv venv --python 3.12 "$VIRTUAL_ENV"

WORKDIR /app

# All pinned requirements files up front: needed for the installs below and for
# setuptools' dynamic-dependency metadata when the app is built (--no-deps only
# skips installing deps, not generating the [laya]/[otel] extra metadata).
COPY requirements.txt laya-requirements.txt otel-requirements.txt ./

# Base runtime deps: fully lockfile-pinned and trim (no torch).
RUN uv pip install --no-cache -r requirements.txt

# The laya engine + torch. laya-requirements.txt pins a CUDA (cu13) build, so
# cuda installs it verbatim (ADR-0002, fully pinned). The trim CPU image cannot
# use those CUDA wheels, so it installs torch from the cpu index instead — the
# accelerator split ADR-0001 anticipates. INSTALL_LAYA=0 skips the whole stack
# for a fast FakeEngine dev image.
ARG INSTALL_LAYA=1
# CPU-only pins (the cuda path uses laya-requirements.txt); keep in sync with it.
ARG LAYA_VERSION=0.3.4
ARG TORCH_VERSION=2.14.0
# A fork spec (git+<url>@<ref>) installs laya from a fork instead of the release.
ARG LAYA_FORK=""
RUN set -eu; \
    if [ "$INSTALL_LAYA" = "1" ]; then \
      case "$ACCEL" in \
        cuda) uv pip install --no-cache -r laya-requirements.txt ;; \
        cpu)  uv pip install --no-cache \
                --extra-index-url https://download.pytorch.org/whl/cpu \
                --index-strategy unsafe-best-match \
                "torch==${TORCH_VERSION}" "laya==${LAYA_VERSION}" ;; \
        *)    echo "unsupported ACCEL=$ACCEL (expected cpu|cuda)" >&2; exit 1 ;; \
      esac; \
      if [ -n "$LAYA_FORK" ]; then \
        echo "Installing laya from fork: $LAYA_FORK"; \
        uv pip install --no-cache --no-deps "$LAYA_FORK"; \
      fi; \
    fi

# Install the app itself into the venv (no dev deps; version pinned so
# setuptools-scm doesn't need the .git tree inside the build).
ARG APP_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION}
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN uv pip install --no-cache --no-deps .

# --------------------------------------------------------------------------- #
# Final: copy only the interpreter + venv (no build tools, no dev deps).
# --------------------------------------------------------------------------- #
FROM base-${ACCEL} AS final

# laya for the real engine images; the dev image overrides this to `fake`.
ARG DEFAULT_ENGINE=laya
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WHATDO_MODEL__ENGINE=${DEFAULT_ENGINE} \
    WHATDO_SERVER__HOST=0.0.0.0 \
    WHATDO_SERVER__PORT=8000

COPY --from=builder /opt/python /opt/python
COPY --from=builder /opt/venv /opt/venv

# Run as a non-root user.
RUN useradd --create-home --uid 10001 laya
USER laya
WORKDIR /home/laya

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"]

CMD ["uvicorn", "whatdo.app:app", "--host", "0.0.0.0", "--port", "8000"]
