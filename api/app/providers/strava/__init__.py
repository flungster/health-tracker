"""Strava provider: adapter + v3 API client (the first, and reference,
provider integration)."""

from app.providers.strava.adapter import StravaAdapter
from app.providers.strava.client import StravaClient

__all__ = ["StravaAdapter", "StravaClient"]
