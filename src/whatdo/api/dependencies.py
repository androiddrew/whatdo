"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from whatdo.config import Settings
from whatdo.inference.pool import WorkerPool
from whatdo.observability import Telemetry


def get_pool(request: Request) -> WorkerPool:
    """The worker pool bound to the app (set in the app factory)."""
    pool: WorkerPool = request.app.state.pool
    return pool


def get_telemetry(request: Request) -> Telemetry:
    """The telemetry facade bound to the app (set in the app factory)."""
    telemetry: Telemetry = request.app.state.telemetry
    return telemetry


def get_settings(request: Request) -> Settings:
    """The settings bound to the app (set in the app factory)."""
    settings: Settings = request.app.state.settings
    return settings
