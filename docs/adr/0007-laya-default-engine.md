# Laya ships with every install and is the default engine

Amends [ADR-0006](0006-uv-project-dependencies.md) and
[ADR-0001](0001-accelerator-build-matrix.md).

Until now `laya` and `torch` lived only in the `cpu`/`cuda` extras, and the engine
setting defaulted to `fake`. A plain `pip install whatdo` therefore produced a server
that started cleanly and answered every request with the **FakeEngine**'s
deterministic, meaningless output. The only hint was an `engine=fake` log line. For
a package whose whole purpose is serving Laya decisions, that default is wrong.

## Decision

- **`laya==0.3.4` and `torch==2.14.0` are base dependencies** in
  `[project.dependencies]`. Every install, including plain `pip install whatdo`,
  can serve the real engine.
- **`model.engine` defaults to `laya`.** `fake` stays a valid value but is
  **testing only**: contract tests, CI, and exercising the HTTP layer without a
  model. It must be selected explicitly (`WHATDO_MODEL__ENGINE=fake`, or tests
  passing `FakeEngine()` to `create_app`). The factory treats `fake` as the
  explicit branch and `laya` as the fallthrough.
- **The accelerator extras only choose the torch wheel.** `cpu` and `cuda` each
  list `torch==2.14.0`, so `[tool.uv.sources]` can still route `cpu` to the PyTorch
  CPU index. They no longer gate whether Laya is installed.
  - `pip install whatdo` gets PyPI's torch: the CUDA-bundled build on Linux (it
    also runs on CPU, but is several GB) and the CPU/MPS build on macOS.
  - CPU-only Linux hosts add
    `--extra-index-url https://download.pytorch.org/whl/cpu`. Pip then prefers
    `2.14.0+cpu`, since a local version sorts after the public one.
  - uv users run `uv sync --extra cpu|cuda` as before.
- **The fake-engine Docker image is removed** (`make build-dev`, the
  `INSTALL_LAYA` and `DEFAULT_ENGINE` build args). Every image ships the real
  engine, and the image no longer sets `WHATDO_MODEL__ENGINE` because the
  application default is already `laya`.
- **Dev and CI environments pass the accelerator extra on every sync.** `uv sync`
  removes extras it isn't given, so the Makefile's `ACCEL` (default `cpu`) is
  passed to `setup`, `test-otel`, `docs` and `docs-serve`. Otherwise CI would
  download PyPI's CUDA torch.

## Consequences

- The base install is large (torch plus transformers). This is accepted: the
  package isn't useful without them.
- `laya` is still imported lazily inside `LayaEngine.load`. Importing the app,
  building engines and the fake-engine test suite never import torch, so the
  fast suite stays fast even though torch is installed.
- Tests that build an app must pass `FakeEngine()` (or `engine="fake"` settings)
  explicitly. Otherwise starting the app loads the real checkpoint.
- `make run` serves the real engine and downloads the checkpoint on first run.
  `WHATDO_MODEL__ENGINE=fake make run` gives a model-free server for HTTP-only
  work.
- `requirements.txt` (the export with no extra) now carries laya and PyPI's torch,
  and is effectively the CUDA stack on Linux. `requirements-cpu.txt` and
  `requirements-cuda.txt` are unchanged in role.

## Considered options

- **Keep the extras, but fail at startup when Laya isn't installed.** Rejected:
  `pip install whatdo` would still produce a server that can't serve, and users
  would have to learn the extras before anything works.
- **Default to the CPU torch wheel for plain pip.** Not possible: package
  metadata can't select an index for pip consumers (`[tool.uv.*]` is uv-local).
