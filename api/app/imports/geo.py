"""Geometry helpers shared by the activity parsers.

Distance and elevation gain are computed here from trackpoints so that every
source format is measured the same way.
"""

import math
from collections.abc import Sequence

from app.imports.parsed import ParsedTrackpoint

_EARTH_RADIUS_M = 6371008.8  # IUGG mean Earth radius


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def compute_distance_m(points: Sequence[ParsedTrackpoint]) -> float | None:
    """Total distance across consecutive points that carry coordinates.

    Returns None when there is not enough coordinate data (for example a
    treadmill run without GPS).
    """
    total = 0.0
    previous: tuple[float, float] | None = None
    for point in points:
        if point.lat is None or point.lon is None:
            continue
        if previous is not None:
            total += haversine_m(previous[0], previous[1], point.lat, point.lon)
        previous = (point.lat, point.lon)
    return total if total > 0 else None


def compute_elevation_gain_m(points: Sequence[ParsedTrackpoint]) -> float | None:
    """Sum of positive altitude changes, in meters.

    Returns None when the samples carry no altitude data.
    """
    gain = 0.0
    previous: float | None = None
    for point in points:
        if point.altitude_m is None:
            continue
        if previous is not None and point.altitude_m > previous:
            gain += point.altitude_m - previous
        previous = point.altitude_m
    return round(gain, 1) if gain > 0 else None
