"""TCX (Training Center XML) activity parser.

A small in-repo parser over the standard library ElementTree (no maintained
Python TCX library exists). Element lookups are by local tag name, so the
parser tolerates the various namespace prefixes vendors use.
"""

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from app.errors.app_error import ActivityImportError
from app.imports.base import ActivityParser
from app.imports.geo import compute_distance_m, compute_elevation_gain_m
from app.imports.parsed import ParsedActivity, ParsedTrackpoint
from app.imports.sports import resolve_sport
from app.imports.timeutil import parse_iso8601, parse_iso_duration_seconds


class TcxParser(ActivityParser):
    """Parses Garmin Training Center XML (.tcx) activity files."""

    source_format = "tcx"

    def supports(self, filename: str, header: bytes) -> bool:
        return filename.lower().endswith(".tcx")

    def parse(self, data: bytes) -> ParsedActivity:
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise ActivityImportError(f"Could not read TCX file: {exc}") from exc

        activity = _find_first(root, "activity")
        if activity is None:
            raise ActivityImportError("TCX file contains no activity.")

        warnings: list[str] = []
        calories = _to_float(_text_of(_find_first(activity, "calories")))

        laps = [child for child in activity if _local_name(child) == "lap"]
        if not laps:
            raise ActivityImportError("TCX activity contains no laps or trackpoints.")

        trackpoints: list[ParsedTrackpoint] = []
        distance_m: float | None = None
        moving_seconds: int | None = None
        started_at = None
        for lap in laps:
            lap_trackpoints = self._parse_lap_trackpoints(lap)
            trackpoints.extend(lap_trackpoints)

            lap_distance = _to_float(_text_of(_find_first(lap, "totaldistancemeters")))
            if lap_distance is not None:
                distance_m = (distance_m or 0.0) + lap_distance

            lap_moving = parse_iso_duration_seconds(_text_of(_find_first(lap, "movingtime")))
            if lap_moving is not None:
                moving_seconds = (moving_seconds or 0) + lap_moving

            lap_start = parse_iso8601(lap.get("StartTime"))
            if started_at is None:
                started_at = lap_start

        if not trackpoints:
            raise ActivityImportError("TCX activity contains no trackpoints.")

        if started_at is None:
            started_at = trackpoints[0].recorded_at
        ended_at = trackpoints[-1].recorded_at
        if started_at is None and ended_at is None:
            warnings.append("TCX trackpoints carried no timestamps.")

        duration_seconds: int | None = None
        if started_at is not None and ended_at is not None:
            duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
        if duration_seconds is None and moving_seconds is not None:
            duration_seconds = moving_seconds

        if distance_m is None:
            distance_m = compute_distance_m(trackpoints)

        return ParsedActivity(
            sport_type=resolve_sport(activity.get("Sport")),
            name=_text_of(_find_first(activity, "name")),
            description=self._description(activity),
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            moving_seconds=moving_seconds,
            distance_m=distance_m,
            calories_kcal=calories,
            elevation_gain_m=compute_elevation_gain_m(trackpoints),
            trackpoints=trackpoints,
            warnings=warnings,
        )

    def _description(self, activity: Element) -> str | None:
        """TCX stores the description in <Notes> (or <Description> in some files)."""
        description = _text_of(_find_first(activity, "notes"))
        if description is None:
            description = _text_of(_find_first(activity, "description"))
        return description

    def _parse_lap_trackpoints(self, lap: Element) -> list[ParsedTrackpoint]:
        track = _find_first(lap, "track")
        if track is None:
            return []
        points: list[ParsedTrackpoint] = []
        for point in track:
            if _local_name(point) == "trackpoint":
                points.append(self._to_trackpoint(point))
        return points

    def _to_trackpoint(self, element: Element) -> ParsedTrackpoint:
        heart_rate_element = _find_first(element, "heartratebpm")
        return ParsedTrackpoint(
            recorded_at=parse_iso8601(_text_of(_find_first(element, "time"))),
            lat=_to_float(_text_of(_find_first(element, "latitudedegrees"))),
            lon=_to_float(_text_of(_find_first(element, "longitudedegrees"))),
            altitude_m=_to_float(_text_of(_find_first(element, "altitudemeters"))),
            # 0 is not a meaningful value for these counters; keep it None.
            heart_rate_bpm=_positive_int(_text_of(heart_rate_element)),
            cadence_rpm=_positive_int(_text_of(_find_first(element, "cadence"))),
            power_w=_positive_int(_text_of(_find_first(element, "power"))),
        )


def _local_name(element: Element) -> str:
    """The element's tag without its namespace, lower-cased."""
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _find_first(root: Element, local_name: str) -> Element | None:
    """The first descendant of ``root`` with the given local tag name."""
    for element in root.iter():
        if _local_name(element) == local_name:
            return element
    return None


def _text_of(element: Element | None) -> str | None:
    """The element's text, or the text of a <Value> child (e.g. HeartRateBpm)."""
    if element is None:
        return None
    if element.text is not None and element.text.strip():
        return element.text.strip()
    for child in element:
        if _local_name(child) == "value" and child.text is not None and child.text.strip():
            return child.text.strip()
    return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    as_float = _to_float(value)
    if as_float is None:
        return None
    return int(round(as_float))


def _positive_int(value: str | None) -> int | None:
    """Round to a positive int, or None for zero/missing values."""
    as_int = _to_int(value)
    if as_int is None or as_int <= 0:
        return None
    return as_int
