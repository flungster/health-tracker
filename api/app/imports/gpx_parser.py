"""GPX (GPS Exchange Format) activity parser, built on gpxpy."""

import io
import xml.etree.ElementTree as ET

import gpxpy
from gpxpy.gpx import GPXException, GPXTrack, GPXTrackPoint

from app.errors.app_error import ActivityImportError
from app.imports.base import ActivityParser, SourceFormat
from app.imports.geo import compute_distance_m, compute_elevation_gain_m
from app.imports.parsed import ParsedActivity, ParsedTrackpoint
from app.imports.sports import resolve_sport
from app.imports.timeutil import to_utc


class GpxParser(ActivityParser):
    """Parses GPS Exchange Format (.gpx) activity files."""

    source_format = SourceFormat.GPX

    def supports(self, filename: str, header: bytes) -> bool:
        return filename.lower().endswith(".gpx")

    def parse(self, data: bytes) -> ParsedActivity:
        try:
            gpx = gpxpy.parse(io.StringIO(data.decode("utf-8", errors="replace")))
        except (ValueError, SyntaxError, GPXException) as exc:
            raise ActivityImportError(f"Could not read GPX file: {exc}") from exc
        if not gpx.tracks:
            raise ActivityImportError("GPX file contains no track data.")

        warnings: list[str] = []
        if len(gpx.tracks) > 1:
            warnings.append("File contains multiple tracks; only the first was imported.")

        track = gpx.tracks[0]
        trackpoints = self._parse_trackpoints(track)
        # Some exporters (Garmin, Polar) put the sport in <trk><type>.
        sport_type = resolve_sport(track.type)

        time_bounds = gpx.get_time_bounds()
        started_at = to_utc(time_bounds.start_time)
        ended_at = to_utc(time_bounds.end_time)
        if time_bounds.start_time is not None and time_bounds.start_time.tzinfo is None:
            warnings.append("GPX timestamps had no timezone; UTC was assumed.")

        moving = gpx.get_moving_data()
        moving_seconds = int(moving.moving_time) if moving.moving_time else None

        duration_seconds: int | None = None
        if started_at is not None and ended_at is not None:
            duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
        if duration_seconds is None:
            duration_seconds = moving_seconds

        # The display name lives in <metadata> for standard files but some
        # exporters put it in <trk><name> instead.
        name = self._clean(gpx.name) or self._clean(track.name)

        return ParsedActivity(
            sport_type=sport_type,
            name=name,
            description=self._clean(gpx.description),
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            moving_seconds=moving_seconds,
            distance_m=compute_distance_m(trackpoints),
            elevation_gain_m=compute_elevation_gain_m(trackpoints),
            trackpoints=trackpoints,
            warnings=warnings,
        )

    def _parse_trackpoints(self, track: GPXTrack) -> list[ParsedTrackpoint]:
        points: list[ParsedTrackpoint] = []
        for segment in track.segments:
            for point in segment.points:
                points.append(self._to_trackpoint(point))
        return points

    def _to_trackpoint(self, point: GPXTrackPoint) -> ParsedTrackpoint:
        extensions = point.extensions
        heart_rate = self._extension_value(extensions, "hr", "heartratebpm")
        cadence = self._extension_value(extensions, "cad", "cadence")
        speed = self._extension_value(extensions, "speed")
        power = self._extension_value(extensions, "power")
        return ParsedTrackpoint(
            recorded_at=to_utc(point.time),
            lat=point.latitude,
            lon=point.longitude,
            altitude_m=point.elevation,
            # 0 is not a meaningful value for these counters; keep it None.
            heart_rate_bpm=self._positive_int(heart_rate),
            cadence_rpm=self._positive_int(cadence),
            speed_mps=speed,
            power_w=self._positive_int(power),
        )

    @staticmethod
    def _positive_int(value: float | None) -> int | None:
        """Round to a positive int, or None for zero/missing values."""
        if value is None or value <= 0:
            return None
        return int(round(value))

    @staticmethod
    def _extension_value(extensions: list[ET.Element] | None, *names: str) -> float | None:
        """Read a numeric value from a trackpoint's vendor extensions.

        Vendor namespaces differ (Garmin gpxtpx, Suunto, Polar...), so the
        value is looked up by local (namespace-free) tag name.
        """
        if not extensions:
            return None
        for container in extensions:
            for name in names:
                element = GpxParser._find_by_local_name(container, name)
                if element is None:
                    continue
                text = GpxParser._text_of(element)
                if text is None:
                    continue
                try:
                    return float(text)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _find_by_local_name(element: ET.Element, local_name: str) -> ET.Element | None:
        for child in element.iter():
            if isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1].lower() == local_name:
                return child
        return None

    @staticmethod
    def _text_of(element: ET.Element) -> str | None:
        """The element's text, or the text of a <Value> child (Suunto style)."""
        if element.text is not None and element.text.strip():
            return element.text.strip()
        for child in element:
            if (
                isinstance(child.tag, str)
                and child.tag.rsplit("}", 1)[-1].lower() == "value"
                and child.text is not None
                and child.text.strip()
            ):
                return child.text.strip()
        return None

    @staticmethod
    def _clean(value: str | None) -> str | None:
        """Trim a file-provided text field; empty becomes None."""
        if value is None:
            return None
        value = value.strip()
        return value or None
