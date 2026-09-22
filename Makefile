UV ?= uv
VENV ?= .venv
BIN := $(VENV)/bin
PY_VERSION ?= 3.12
HOST ?= 127.0.0.1
PORT ?= 8000

# Image build knobs (ADR-0001). IMAGE/TAG name the image; LAYA_FORK, when set to
# a `git+…@ref` spec, installs laya from a fork instead of the pinned release.
IMAGE ?= whatdo
TAG ?= dev
DOCKER ?= docker
LAYA_FORK ?=
FORK_BUILD_ARG := $(if $(LAYA_FORK),--build-arg LAYA_FORK="$(LAYA_FORK)",)

# Load-test knobs (#12). Point BASE_URL at a running deployment; set API_KEY if
# it runs with auth enabled. Passed through to k6 as environment variables.
K6 ?= k6
BASE_URL ?= http://localhost:8000
API_KEY ?=
K6_ENV := -e BASE_URL=$(BASE_URL) $(if $(API_KEY),-e API_KEY=$(API_KEY),)

.PHONY: setup compile lint fmt typecheck test test-otel test-slow run \
	build-cpu build-cuda build-dev docs docs-serve load-test

## Create the dev virtualenv, install pinned dev deps + the package, install git hooks.
setup:
	$(UV) venv --python $(PY_VERSION)
	$(UV) pip install -r dev-requirements.txt
	$(UV) pip install -e . --no-deps
	git config core.hooksPath .githooks
	@echo "Dev environment ready. Git hooks -> .githooks (pre-push runs the fast suite)."

## Recompile the pinned requirements .txt files from the .in sources.
compile:
	$(UV) pip compile requirements.in -o requirements.txt
	$(UV) pip compile dev-requirements.in -o dev-requirements.txt
	$(UV) pip compile otel-requirements.in -o otel-requirements.txt
	$(UV) pip compile laya-requirements.in -o laya-requirements.txt
	$(UV) pip compile docs-requirements.in -o docs-requirements.txt

## Lint + format check (no changes).
lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

## Auto-format and auto-fix.
fmt:
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

## Static type checking (strict on the package).
typecheck:
	$(BIN)/mypy

## Fast test suite (excludes GPU/real-model tests).
test:
	$(BIN)/pytest -m "not slow"

## Install the [otel] extra, then run the suite so the OTEL-on tests execute.
test-otel:
	$(UV) pip install -e '.[otel]'
	$(BIN)/pytest -m "not slow"

## Slow suite: real Laya engine on real checkpoints. Requires a GPU; run locally.
test-slow:
	$(BIN)/pytest -m slow

## Run the app locally with autoreload.
run:
	$(BIN)/uvicorn whatdo.app:app --host $(HOST) --port $(PORT) --reload

## Build the trim CPU image. Pass LAYA_FORK=git+<url>@<ref> to use a laya fork.
build-cpu:
	$(DOCKER) build --build-arg ACCEL=cpu $(FORK_BUILD_ARG) -t $(IMAGE):cpu-$(TAG) .

## Build the CUDA image (builds on CPU-only hosts; running inference needs a GPU).
build-cuda:
	$(DOCKER) build --build-arg ACCEL=cuda $(FORK_BUILD_ARG) -t $(IMAGE):cuda-$(TAG) .

## Build the fast dev image: CPU base, laya/torch skipped, FakeEngine default.
build-dev:
	$(DOCKER) build --build-arg ACCEL=cpu \
		--build-arg INSTALL_LAYA=0 --build-arg DEFAULT_ENGINE=fake \
		-t $(IMAGE):dev .

## Build the sdist + wheel into dist/ (version derived by setuptools-scm).
dist:
	rm -rf dist
	$(UV) build
## Build the documentation site (strict — matches CI). Needs docs-requirements.txt.
docs:
	$(BIN)/mkdocs build --strict

## Serve the docs locally with live reload.
docs-serve:
	$(BIN)/mkdocs serve

## Run the k6 load tests against a running deployment (needs k6; not gated in CI).
## Point at a real-model server: make load-test BASE_URL=... [API_KEY=...]
load-test:
	$(K6) run $(K6_ENV) tests/load/smoke.js
	$(K6) run $(K6_ENV) tests/load/load.js
