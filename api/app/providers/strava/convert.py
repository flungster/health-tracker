"""Convert Strava activity JSON into the app's format-neutral ParsedActivity.

Pure: a decoded Strava full-activity response (``GET /activities/{id}``) in,
a ``ParsedActivity`` out. Null-safe throughout — missing fields stay ``None``
and are recorded in ``ParsedActivity.warnings`` where they matter.
"""

from datetime import datetime, timedelta
from typing import Any

from app.imports.parsed import ParsedActivity, ParsedSportMetrics, ParsedTrackpoint
from app.imports.timeutil import parse_iso8601

# Strava sport_type -> canonical activity type (activity_types.value).
# Types not listed here map to "other" (with a warning).
SPORT_TYPE_MAP: dict[str, str] = {
    "Running": "running",
    "TrailRun": "running",
    "VirtualRun": "running",
    "Canicross": "running",
    "Cycling": "cycling",
    "GravelRide": "cycling",
    "MountainBike": "cycling",
    "EBikeRide": "cycling",
    "Ride": "cycling",
    "Spin": "cycling",
    "Handcycle": "cycling",
    "Velomobile": "cycling",
    "Rowing": "rowing",
    "VirtualRowing": "rowing",
    "Yoga": "yoga",
    "Pilates": "yoga",
    "Strength": "strength",
    "Gym": "strength",
    "WeightLifting": "strength",
    "Crossfit": "strength",
    "Kickboxing": "strength",
    "MartialArts": "strength",
    "Swim": "swimming",
    "OpenWaterSwim": "swimming",
    "Walking": "walking",
    "Hike": "hiking",
    "Hiking": "hiking",
}
UNKNOWN_SPORT_TYPE = "other"


def strava_activity_to_parsed(data: dict[str, Any]) -> ParsedActivity:
    """Convert one Strava full-activity response (dynamic JSON, narrowed here)."""
    warnings: list[str] = []

    sport_type = _map_sport(data.get("sport_type"), warnings)

    started_at = parse_iso8601(_as_str(data.get("start_date")))
    elapsed = _seconds(data.get("elapsed_time"))
    moving = _seconds(data.get("moving_time"))
    ended_at = None
    if started_at is not None and elapsed is not None:
        ended_at = started_at + timedelta(seconds=elapsed)

    # Trackpoint times are offsets in seconds from the start, not absolute.
    trackpoints = _map_trackpoints(data.get("track_points"), started_at)

    heart_rate_avg = _positive_int(data.get("average_heartrate"))
    heart_rate_max = _positive_int(data.get("max_heartrate"))
    if data.get("heartrate_opt_out") is True:
        warnings.append("The athlete has hidden heart rate on Strava; no HR data was imported.")
        heart_rate_avg = None
        heart_rate_max = None

    return ParsedActivity(
        sport_type=sport_type,
        name=_as_str(data.get("name")),
        description=_as_str(data.get("description")),
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=elapsed,
        moving_seconds=moving,
        # 0 is not a meaningful value for these (strength work reports 0);
        # keep them None, mirroring the file parsers' convention.
        distance_m=_positive_float(data.get("distance")),
        calories_kcal=_positive_float(data.get("calories")),
        elevation_gain_m=_positive_float(data.get("total_elevation_gain")),
        # Summary HR doubles as the fallback when trackpoints carry no HR
        # samples (same convention as the file parsers + ActivityStatistics).
        heart_rate_avg_bpm=heart_rate_avg,
        heart_rate_max_bpm=heart_rate_max,
        cadence_avg_rpm=_positive_int(data.get("average_cadence")),
        trackpoints=trackpoints,
        sport_metrics=ParsedSportMetrics(
            power_avg_w=_positive_int(data.get("average_watts")),
            power_max_w=_positive_int(data.get("max_watts")),
        ),
        warnings=warnings,
    )


def _map_sport(value: Any, warnings: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    mapped = SPORT_TYPE_MAP.get(value)
    if mapped is not None:
        return mapped
    warnings.append(f"Unknown Strava sport type {value!r}; imported as {UNKNOWN_SPORT_TYPE!r}.")
    return UNKNOWN_SPORT_TYPE


def _map_trackpoints(raw: Any, started_at: datetime | None) -> list[ParsedTrackpoint]:
    if not isinstance(raw, list):
        return []
    points: list[ParsedTrackpoint] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        offset = _seconds(entry.get("time"))
        recorded_at = None
        if started_at is not None and offset is not None:
            recorded_at = started_at + timedelta(seconds=offset)
        points.append(
            ParsedTrackpoint(
                recorded_at=recorded_at,
                lat=_float(entry.get("latitude")),
                lon=_float(entry.get("longitude")),  # negative longitudes = west
                altitude_m=_float(entry.get("altitude")),
                heart_rate_bpm=_positive_int(entry.get("heart_rate")),
                cadence_rpm=_positive_int(entry.get("cadence")),
                speed_mps=_non_negative_float(entry.get("speed")),
                power_w=_positive_int(entry.get("watts")),
            )
        )
    return points


def _as_str(value: Any) -> str | None:
    """A non-empty trimmed string, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _seconds(value: Any) -> int | None:
    """A non-negative integer number of seconds, or None."""
    number = _number(value)
    if number is None or number < 0:
        return None
    return int(number)


def _positive_int(value: Any) -> int | None:
    """A positive int, or None for zero/negative/missing (mirrors the parsers)."""
    number = _number(value)
    if number is None or number <= 0:
        return None
    return int(round(number))


def _non_negative_float(value: Any) -> float | None:
    number = _number(value)
    if number is None or number < 0:
        return None
    return number


def _positive_float(value: Any) -> float | None:
    """A positive float, or None for zero/negative/missing."""
    number = _number(value)
    if number is None or number <= 0:
        return None
    return number


def _float(value: Any) -> float | None:
    return _number(value)


def _number(value: Any) -> float | None:
    """str/bool are rejected; int/float (and numeric strings) are accepted."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
