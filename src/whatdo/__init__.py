"""whatdo: a Typesafe-compatible Jev API server backed by the Laya engine."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("whatdo")
except PackageNotFoundError:  # pragma: no cover - not installed (e.g. source checkout)
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
