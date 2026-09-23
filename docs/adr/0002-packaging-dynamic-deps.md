# Dependencies live in requirements files, referenced dynamically by pyproject

> **Superseded by [ADR-0006](0006-uv-project-dependencies.md) (2026-09-23).** Dependencies are
> now declared inline in `pyproject.toml` (PEP 621) with dev/docs in PEP 735 groups and a
> committed `uv.lock`; the `.in`/`.txt` files and setuptools dynamic dependencies are gone. This
> ADR is kept for historical context.

The project pins dependencies in `requirements.in`/`dev-requirements.in`/`otel-requirements.in` (compiled with uv to `.txt`), not inline in `pyproject.toml`. But the package must be `pip install`-able with an `[otel]` extra, which normally requires dependencies *in* `pyproject.toml`. We reconcile this with **setuptools dynamic dependencies**: `pyproject.toml` declares `dynamic = ["dependencies", "optional-dependencies"]` and points at the requirements files, so the deps still live in the requirements files while `pip install "whatdo[otel]"` works. OTEL imports are lazily guarded so the base install runs without the OTEL libraries.

## Considered options

- **Deps inline in pyproject** — rejected: contradicts the requirement that deps live in requirements files.
- **No pyproject deps, image-only distribution** — rejected: breaks `pip install whatdo[otel]`.
- **setuptools-scm** derives the version from `vX.Y.Z` git tags, keeping version out of source too.
