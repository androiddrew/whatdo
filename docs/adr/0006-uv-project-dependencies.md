# Dependencies managed by uv project mode (pyproject + uv.lock)

Supersedes [ADR-0002](0002-packaging-dynamic-deps.md). Cooperates with
[ADR-0001](0001-accelerator-build-matrix.md) (the accelerator build matrix).
Amended by [ADR-0007](0007-laya-default-engine.md): `laya` and `torch` are now base
dependencies, and the accelerator extras only choose the torch wheel.

We moved off the pip-tools–style workflow (abstract `*.in` files compiled to pinned `*.txt`
via `uv pip compile`, pulled into `pyproject.toml` with setuptools *dynamic dependencies*). That
split predated modern standards and left the CPU torch build **unlocked** (installed ad hoc at
Docker build time). We now use **uv project mode** with a single, cross-platform lockfile.

## Decision

- **Dependencies are declared inline** in `pyproject.toml` (PEP 621): `[project.dependencies]`
  for runtime, `[project.optional-dependencies]` for the `otel` and accelerator extras. Only the
  version stays `dynamic` (setuptools-scm, from git tags). The build backend is unchanged
  (setuptools + setuptools-scm).
- **Dev/docs tooling moves to PEP 735 `[dependency-groups]`** (`dev`, `docs`) — not extras,
  because nobody `pip install`s them. They are **not** part of the published package metadata.
- **`uv.lock` is the single source of truth** — one universal, cross-platform lock resolved with
  environment markers. Committed. `make lock` refreshes it; CI enforces sync via `uv lock --check`.
- **Accelerator = conflicting extras.** `cpu` and `cuda` (future `rocm`/`jetson`) each pin one
  torch version; the *wheel* is chosen per accelerator by index — `[[tool.uv.index]]` +
  `[tool.uv.sources]` route the `cpu` extra to the PyTorch CPU index while `cuda` uses the default
  PyPI torch (bundled cu13 nvidia wheels). `[tool.uv].conflicts` marks them mutually exclusive, so
  the lock captures **both** resolutions — including CPU, which ADR-0002 left unpinned.
- **`laya` always resolves from PyPI** in project metadata. The **fork stays a Docker-only
  build-time option** (`LAYA_FORK` arg, installed over the stack); it is never a package
  dependency. This keeps `whatdo` **publish-ready**: no direct-reference (`git+…`/URL) deps in the
  built wheel's metadata (PyPI rejects those). Publishing to PyPI itself is **deferred** to a
  future round — no publish pipeline is added here.
- **Three consistent install layers** (nobody is forced to use uv):
  1. **uv** — `uv sync` / `uv sync --extra cpu|cuda` (index selection is automatic).
  2. **raw pip** — the extras are the contract; name the index explicitly, e.g.
     `pip install "whatdo[cpu]" --extra-index-url https://download.pytorch.org/whl/cpu`
     (`[tool.uv.*]` is local config and does not reach pip consumers).
  3. **fully-pinned / reproducible** — per-accelerator `requirements-*.txt` exported from the lock
     by `make lock` (`requirements.txt` base, `requirements-cpu.txt`, `requirements-cuda.txt`);
     `pip install -r` reproduces the exact versions with no uv required.

## Consequences

- The Docker builder installs from the per-accelerator export (`requirements-${ACCEL}.txt`),
  collapsing the old cpu/cuda branching; the `LAYA_FORK` override is preserved.
- `make setup` is now `uv sync`; `make compile` is replaced by `make lock` (lock + exports).
- Adding a new accelerator = a new extra + its index/source + a conflict entry + an export line.

## Considered options

- **Keep pip-tools (`.in`/`.txt`)** — rejected: the holdover this ADR removes; CPU stayed unlocked.
- **Model the fork as a direct git URL in an extra** — rejected: legal only while unpublished;
  it would make the wheel unpublishable to PyPI. The fork lives in the `LAYA_FORK` Docker arg.
- **Push accelerator selection entirely into Docker (as ADR-0001 did)** — rejected: leaves CPU
  unreproducible and pins torch in two places; the lock now covers every accelerator.
