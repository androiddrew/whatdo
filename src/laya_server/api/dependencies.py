"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from laya_server.config import Settings
from laya_server.inference.pool import WorkerPool


def get_pool(request: Request) -> WorkerPool:
    """The worker pool bound to the app (set in the app factory)."""
    pool: WorkerPool = request.app.state.pool
    return pool


def get_settings(request: Request) -> Settings:
    """The settings bound to the app (set in the app factory)."""
    settings: Settings = request.app.state.settings
    return settings
