"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from laya_server.inference.base import DecisionEngine


def get_engine(request: Request) -> DecisionEngine:
    """The inference engine bound to the app (set in the app factory)."""
    engine: DecisionEngine = request.app.state.engine
    return engine
