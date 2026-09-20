UV ?= uv
VENV ?= .venv
BIN := $(VENV)/bin
PY_VERSION ?= 3.12
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: setup compile lint fmt typecheck test test-slow run

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

## Slow suite: real Laya engine on real checkpoints. Requires a GPU; run locally.
test-slow:
	$(BIN)/pytest -m slow

## Run the app locally with autoreload.
run:
	$(BIN)/uvicorn laya_server.app:app --host $(HOST) --port $(PORT) --reload
