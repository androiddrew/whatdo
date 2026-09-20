"""Model resolution: map a requested Jev Model id to this deployment's Served Model.

A deployment serves exactly one Served Model (ADR-0004). Resolution order:

1. The always-on compatibility shim: ``jev-latest`` / ``jev-preview`` -> the
   served model, so the unconfigured official SDK works out of the box.
2. The feature-flagged, configurable Alias Table (operator-defined ids).
3. A direct match against the served model (``auto`` or a raw ``laya-*`` name).

Anything else is not served by this deployment and raises ``ModelNotServedError``.
"""

from __future__ import annotations

from laya_server.config import ModelSettings

# The SDK's default model ids; always resolved to the served model.
SHIM_ALIASES = ("jev-latest", "jev-preview")


class ModelNotServedError(Exception):
    """Raised when a requested Model is not served by this deployment."""

    def __init__(self, requested: str, served: str) -> None:
        self.requested = requested
        self.served = served
        super().__init__(
            f"model {requested!r} is not served by this deployment (serves {served!r})"
        )


def accepted_models(settings: ModelSettings) -> list[str]:
    """Every Model id this deployment accepts, in listing order.

    This is the single authority on acceptance, consumed by both resolution and
    the ``/v1/models`` listing so the advertised set can never drift from the
    resolvable set. All accepted ids resolve to the one served model; alias-table
    entries are honored only when they target the served model, upholding the
    one-served-model invariant (ADR-0004).
    """
    served = settings.served_model
    names = [served, *SHIM_ALIASES]
    if settings.alias_table_enabled:
        names += [
            alias for alias, target in settings.alias_table.items() if target == served
        ]
    return names


def resolve_model(requested: str, settings: ModelSettings) -> str:
    """Resolve ``requested`` to the served-model id, or raise if not served."""
    if requested in accepted_models(settings):
        return settings.served_model
    raise ModelNotServedError(requested, settings.served_model)
