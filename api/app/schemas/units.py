"""Unit systems and display-unit conversions.

Storage is always SI (see the data model). These pure helpers convert stored
SI values to a user's display unit system for API views only — the database is
never written in imperial units. All factors are exact definitions (the
international mile, foot and pound), so no information is lost by converting at
read time. The API sends unrounded values; rounding to display precision is a
client concern (M14c).
"""

from datetime import datetime
from enum import StrEnum


class UnitSystem(StrEnum):
    """The display unit systems a user can select."""

    METRIC = "metric"
    IMPERIAL = "imperial"


# Exact unit definitions.
MILE_METERS = 1609.344  # one mile, in meters
FOOT_METERS = 0.3048  # one foot, in meters
POUND_KILOGRAMS = 0.45359237  # one pound, in kilograms


def units_for(imperial_enabled_at: datetime | None) -> UnitSystem:
    """The display system implied by a stored setting.

    ``imperial_enabled_at`` is the user profile's timestamp: set (imperial in
    effect since that instant) or unset/None (metric, the default). The single
    derivation point for both user and activity views.
    """
    if imperial_enabled_at is not None:
        return UnitSystem.IMPERIAL
    return UnitSystem.METRIC


def display_distance(meters: float | None, units: UnitSystem) -> float | None:
    """A distance in the display system (meters or miles)."""
    if meters is None:
        return None
    if units is UnitSystem.IMPERIAL:
        return meters / MILE_METERS
    return meters


def display_elevation_gain(meters: float | None, units: UnitSystem) -> float | None:
    """An elevation gain in the display system (meters or feet)."""
    if meters is None:
        return None
    if units is UnitSystem.IMPERIAL:
        return meters / FOOT_METERS
    return meters


def display_altitude(meters: float | None, units: UnitSystem) -> float | None:
    """An altitude in the display system (meters or feet)."""
    if meters is None:
        return None
    if units is UnitSystem.IMPERIAL:
        return meters / FOOT_METERS
    return meters


def display_speed(meters_per_second: float | None, units: UnitSystem) -> float | None:
    """A speed in the display system (m/s or mph)."""
    if meters_per_second is None:
        return None
    if units is UnitSystem.IMPERIAL:
        # (meters per second) * (seconds per hour) / (meters per mile).
        return meters_per_second * 3600.0 / MILE_METERS
    return meters_per_second


def display_pace_seconds(seconds_per_km: float | None, units: UnitSystem) -> float | None:
    """A pace in seconds per display distance unit (km when metric, mi otherwise)."""
    if seconds_per_km is None:
        return None
    if units is UnitSystem.IMPERIAL:
        # A mile is exactly 1.609344 km, so the pace per mile scales by that
        # exact factor.
        return seconds_per_km * (MILE_METERS / 1000.0)
    return seconds_per_km


def display_weight(kilograms: float | None, units: UnitSystem) -> float | None:
    """A weight in the display system (kg or lb)."""
    if kilograms is None:
        return None
    if units is UnitSystem.IMPERIAL:
        return kilograms / POUND_KILOGRAMS
    return kilograms
