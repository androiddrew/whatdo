# Accelerator build matrix via a single parametrized Dockerfile

Amended by [ADR-0007](0007-laya-default-engine.md): every image ships the real Laya
engine; the fake-engine dev image is gone.

Laya runs on several accelerators, and we want CPU and CUDA now with ROCm and Jetson later. We use **one multi-stage Dockerfile parametrized by an `ACCEL` build arg** (selecting base image + torch index) rather than a Dockerfile per target, because the build stages are otherwise identical and per-target files drift out of sync. `cpu` and `cuda` are implemented and built in CI; `rocm` and `jetson` exist as documented, unbuilt slots until we have hardware to validate them.

## Consequences

- The GPU/CUDA image is necessarily large (multi-GB torch wheels); only the `cpu` image is genuinely "trim." This is accepted — "trim dependencies" applies to the CPU default, not the accelerator variants.
- CI can build the CUDA image on CPU-only runners (building needs no GPU); only *running* real inference needs one.
