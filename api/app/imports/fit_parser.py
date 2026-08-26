"""FIT (Fitness ID Technology) activity parser, built on fitdecode."""

import io
from datetime import UTC, datetime
from typing import Any

import fitdecode  # type: ignore[import-untyped]
from fitdecode import FitDataMessage
from fitdecode.exceptions import FitError  # type: ignore[import-untyped]

from app.errors.app_error import ActivityImportError
from app.imports.base import ActivityParser, SourceFormat
from app.imports.parsed import ParsedActivity, ParsedSportMetrics, ParsedTrackpoint
from app.imports.sports import resolve_sport
from app.imports.timeutil import to_utc

#: FIT sport enum values (for files whose sport is not decoded to a string).
_FIT_SPORT_BY_VALUE: dict[int, str] = {
    0: "running",
    1: "cycling",
    3: "walking",
    4: "other",  # fitness_equipment
    5: "rowing",
    6: "swimming",
    14: "hiking",
    26: "yoga",
    29: "strength",  # core_training
    126: "strength",  # strength_training (newer FIT profiles)
}


class FitParser(ActivityParser):
    """Parses Garmin/FIT (.fit) activity files."""

    source_format = SourceFormat.FIT

    def supports(self, filename: str, header: bytes) -> bool:
        if len(header) >= 12 and header[0] in (0x0C, 0x0E) and header[8:12] == b".FIT":
            return True
        return filename.lower().endswith(".fit")

    def parse(self, data: bytes) -> ParsedActivity:
        try:
            records, session = self._read_messages(data)
        except FitError as exc:
            raise ActivityImportError(f"Could not read FIT file: {exc}") from exc

        if not records and session is None:
            raise ActivityImportError("FIT file contains no activity data.")

        warnings: list[str] = []
        trackpoints = [self._to_trackpoint(record) for record in records]

        started_at = None
        ended_at = None
        for point in trackpoints:
            if started_at is None and point.recorded_at is not None:
                started_at = point.recorded_at
            if point.recorded_at is not None:
                ended_at = point.recorded_at

        return ParsedActivity(
            sport_type=self._resolve_sport(session),
            name=None,
            description=None,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=self._session_seconds(session, "total_elapsed_time"),
            moving_seconds=self._session_seconds(session, "moving_time"),
            distance_m=self._session_float(session, "total_distance"),
            calories_kcal=self._session_float(session, "total_calories"),
            elevation_gain_m=self._session_float(session, "total_ascent"),
            heart_rate_avg_bpm=self._session_int(session, "avg_heart_rate"),
            heart_rate_max_bpm=self._session_int(session, "max_heart_rate"),
            sport_metrics=ParsedSportMetrics(
                power_avg_w=self._session_int(session, "avg_power"),
                power_max_w=self._session_int(session, "max_power"),
            ),
            trackpoints=trackpoints,
            warnings=warnings,
        )

    def _read_messages(self, data: bytes) -> tuple[list[FitDataMessage], FitDataMessage | None]:
        """Decode the file and keep its record messages plus the first session."""
        records: list[FitDataMessage] = []
        session: FitDataMessage | None = None
        reader = fitdecode.FitReader(
            io.BytesIO(data),
            check_crc=fitdecode.CrcCheck.RAISE,
            error_handling=fitdecode.ErrorHandling.RAISE,
        )
        with reader:
            for frame in reader:
                if frame.frame_type != fitdecode.FIT_FRAME_DATAMESG:
                    continue
                if frame.name == "record":
                    records.append(frame)
                elif frame.name == "session" and session is None:
                    session = frame
        return records, session

    def _resolve_sport(self, session: FitDataMessage | None) -> str | None:
        if session is None or not session.has_field("sport"):
            return None
        sport = session.get_value("sport")
        if isinstance(sport, str):
            return resolve_sport(sport)
        if isinstance(sport, int) and not isinstance(sport, bool):
            return _FIT_SPORT_BY_VALUE.get(sport, "other")
        return None

    def _to_trackpoint(self, record: FitDataMessage) -> ParsedTrackpoint:
        return ParsedTrackpoint(
            recorded_at=self._as_datetime(record, "timestamp"),
            lat=self._as_coordinate(record, "position_lat", 90.0),
            lon=self._as_coordinate(record, "position_long", 180.0),
            altitude_m=self._as_float(record, "altitude"),
            # 0 is a "no data" sentinel for these counters (e.g. while
            # standing still at the start) and is not a meaningful value.
            heart_rate_bpm=self._as_positive_int(record, "heart_rate"),
            cadence_rpm=self._as_positive_int(record, "cadence"),
            speed_mps=self._as_float(record, "speed"),
            power_w=self._as_positive_int(record, "power"),
        )

    def _as_positive_int(self, record: FitDataMessage, field_name: str) -> int | None:
        value = self._as_int(record, field_name)
        if value is None or value <= 0:
            return None
        return value

    def _field(self, message: FitDataMessage, field_name: str) -> Any:
        """The decoded value of ``field_name`` in ``message``, or None."""
        if not message.has_field(field_name):
            return None
        return message.get_value(field_name)

    def _session_seconds(self, session: FitDataMessage | None, field_name: str) -> int | None:
        return self._as_int_value(self._field(session, field_name)) if session else None

    def _session_int(self, session: FitDataMessage | None, field_name: str) -> int | None:
        return self._as_int_value(self._field(session, field_name)) if session else None

    def _session_float(self, session: FitDataMessage | None, field_name: str) -> float | None:
        return self._as_float_value(self._field(session, field_name)) if session else None

    def _as_datetime(self, record: FitDataMessage, field_name: str) -> datetime | None:
        return self._as_datetime_value(self._field(record, field_name))

    def _as_float(self, record: FitDataMessage, field_name: str) -> float | None:
        return self._as_float_value(self._field(record, field_name))

    def _as_int(self, record: FitDataMessage, field_name: str) -> int | None:
        return self._as_int_value(self._field(record, field_name))

    def _as_coordinate(self, record: FitDataMessage, field_name: str, limit: float) -> float | None:
        """Decode a FIT position value (raw int is degrees x 1e-7 per the FIT spec)."""
        value = self._field(record, field_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if abs(value) > limit:
            value = value / 10000000.0
        if abs(value) > limit:
            return None
        return float(value)

    @staticmethod
    def _as_datetime_value(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return to_utc(value)
        if isinstance(value, int) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, tz=UTC)
        return None

    @staticmethod
    def _as_float_value(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @staticmethod
    def _as_int_value(value: Any) -> int | None:
        as_float = FitParser._as_float_value(value)
        if as_float is None:
            return None
        return int(round(as_float))
