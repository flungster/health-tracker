"""The API version, read from the installed package metadata."""

import importlib.metadata

try:
    _version: str = importlib.metadata.version("health-tracker-api")
except importlib.metadata.PackageNotFoundError:  # running without `uv sync` installed the package
    _version = "unknown"


def api_version() -> str:
    """Return the installed API package version (e.g. ``0.1.0``)."""
    return _version
