"""Optional OpenTelemetry observability (ticket #8, ADR-0005).

Guarded imports keep OTEL out of the base install; ``laya-server[otel]`` pulls
in the libraries. Everything is off unless ``LAYA_OTEL__ENABLED`` is set.
"""

from __future__ import annotations

from laya_server.observability.setup import (
    configure_observability,
    shutdown_observability,
)
from laya_server.observability.telemetry import Telemetry

__all__ = ["Telemetry", "configure_observability", "shutdown_observability"]
