"""Tests for the activity file import package (parsers, detection, helpers)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.errors.app_error import ActivityImportError
from app.imports import (
    FitParser,
    GpxParser,
    TcxParser,
    build_default_detector,
    resolve_sport,
)
from app.imports.geo import compute_distance_m, compute_elevation_gain_m, haversine_m
from app.imports.parsed import ParsedTrackpoint
from app.imports.timeutil import parse_iso8601, parse_iso_duration_seconds

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestGpxParser:
    def test_parses_running_fixture(self) -> None:
        activity = GpxParser().parse(_read("run_sample.gpx"))

        assert activity.name == "Morning Run"
        assert activity.description == "Fixture run for parser tests"
        assert activity.sport_type is None  # file carries no <type>
        assert activity.started_at == datetime(2024, 6, 1, 9, 0, 0, tzinfo=UTC)
        assert activity.ended_at == datetime(2024, 6, 1, 9, 24, 40, tzinfo=UTC)
        assert activity.duration_seconds == 1480
        assert activity.moving_seconds is not None
        assert activity.moving_seconds > 0
        assert activity.moving_seconds <= activity.duration_seconds
        assert len(activity.trackpoints) == 75

        first = activity.trackpoints[0]
        assert first.lat == pytest.approx(48.8500, abs=1e-6)
        assert first.lon == pytest.approx(2.3500, abs=1e-6)
        assert first.altitude_m == pytest.approx(40.0, abs=0.1)
        assert first.heart_rate_bpm == 120
        assert first.cadence_rpm == 170

        heart_rates = [p.heart_rate_bpm for p in activity.trackpoints if p.heart_rate_bpm]
        assert max(heart_rates) == 160
        assert min(heart_rates) == 120

        # 75 samples x ~66 m steps ~= 5 km
        assert activity.distance_m is not None
        assert 4500 < activity.distance_m < 5600
        assert activity.elevation_gain_m is not None
        assert activity.elevation_gain_m > 0
        assert activity.warnings == []

    def test_parses_sport_type_and_non_utc_time(self) -> None:
        gpx = (
            '<?xml version="1.0"?>'
            '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
            "<trk><type>Run Mode</type><trkseg>"
            '<trkpt lat="10.0" lon="20.0"><time>2024-01-01T00:00:00+02:00</time></trkpt>'
            '<trkpt lat="10.001" lon="20.001"><time>2024-01-01T00:00:10+02:00</time></trkpt>'
            "</trkseg></trk>"
            "</gpx>"
        )
        activity = GpxParser().parse(gpx.encode("utf-8"))
        assert activity.sport_type == "running"
        assert activity.started_at == datetime(2023, 12, 31, 22, 0, 0, tzinfo=UTC)

    def test_rejects_malformed_gpx(self) -> None:
        with pytest.raises(ActivityImportError):
            GpxParser().parse(b"<gpx><trk")

    def test_rejects_gpx_without_tracks(self) -> None:
        with pytest.raises(ActivityImportError):
            GpxParser().parse(b'<?xml version="1.0"?><gpx version="1.1" />')


class TestTcxParser:
    def test_parses_cycling_fixture(self) -> None:
        activity = TcxParser().parse(_read("cycle_sample.tcx"))

        assert activity.sport_type == "cycling"
        assert activity.name == "Evening Ride"
        assert activity.description == "Fixture ride with power"
        assert activity.started_at == datetime(2024, 6, 15, 17, 30, 0, tzinfo=UTC)
        assert activity.ended_at == datetime(2024, 6, 15, 17, 39, 55, tzinfo=UTC)
        assert activity.duration_seconds == 595
        assert activity.moving_seconds == 595
        assert activity.distance_m == pytest.approx(6666.7)
        assert activity.calories_kcal == pytest.approx(320.0)
        assert len(activity.trackpoints) == 120

        first = activity.trackpoints[0]
        assert first.heart_rate_bpm == 130
        assert first.cadence_rpm == 90
        assert first.power_w == 200
        powers = [p.power_w for p in activity.trackpoints if p.power_w is not None]
        assert max(powers) == 240
        assert activity.elevation_gain_m is not None
        assert activity.warnings == []

    def test_rejects_malformed_tcx(self) -> None:
        with pytest.raises(ActivityImportError):
            TcxParser().parse(b"this is not xml")

    def test_rejects_tcx_without_activity(self) -> None:
        with pytest.raises(ActivityImportError):
            TcxParser().parse(b'<?xml version="1.0"?><SomeOtherFile />')


class TestFitParser:
    def test_parses_running_fixture(self) -> None:
        activity = FitParser().parse(_read("run_garmin_fenix5.fit"))

        assert activity.sport_type == "running"
        assert len(activity.trackpoints) > 0
        assert activity.started_at is not None
        assert activity.started_at.year == 2017
        assert activity.duration_seconds is not None
        assert activity.duration_seconds > 0
        assert activity.distance_m is not None
        assert activity.heart_rate_max_bpm is not None
        assert activity.heart_rate_avg_bpm is not None
        assert activity.heart_rate_max_bpm >= activity.heart_rate_avg_bpm

        # Position decoding: raw FIT integers are degrees x 1e-7.
        first = activity.trackpoints[0]
        assert first.lat is not None
        assert first.lon is not None
        assert -90 <= first.lat <= 90
        assert -180 <= first.lon <= 180

    def test_parses_cycling_fixture(self) -> None:
        activity = FitParser().parse(_read("cycle_garmin_fenix5.fit"))
        assert activity.sport_type == "cycling"
        assert len(activity.trackpoints) > 0
        assert activity.heart_rate_max_bpm is not None


class _StubFitMessage:
    """Mimics the fitdecode FitDataMessage surface used by FitParser."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def has_field(self, field_name: str) -> bool:
        return field_name in self._values

    def get_value(self, field_name: str, **kwargs: object) -> object:
        return self._values.get(field_name)


class TestFitParserPowerPath:
    def test_session_power_maps_to_sport_metrics(self) -> None:
        parser = FitParser()
        session = _StubFitMessage({"sport": "cycling", "avg_power": 210, "max_power": 350})
        assert parser._resolve_sport(session) == "cycling"
        assert parser._session_int(session, "avg_power") == 210
        assert parser._session_int(session, "max_power") == 350

    def test_trackpoint_power_is_decoded(self) -> None:
        parser = FitParser()
        record = _StubFitMessage({"power": 240, "heart_rate": 150, "cadence": 92, "speed": 6.5})
        point = parser._to_trackpoint(record)
        assert point.power_w == 240
        assert point.heart_rate_bpm == 150
        assert point.cadence_rpm == 92
        assert point.speed_mps == 6.5

    def test_rejects_corrupt_crc(self) -> None:
        with pytest.raises(ActivityImportError):
            FitParser().parse(_read("fit_corrupt_crc.fit"))

    def test_rejects_truncated_file(self) -> None:
        with pytest.raises(ActivityImportError):
            FitParser().parse(_read("fit_truncated.fit"))


class TestFormatDetector:
    def test_detects_by_extension(self) -> None:
        detector = build_default_detector()
        assert isinstance(detector.detect("run.gpx", b"<?xml"), GpxParser)
        assert isinstance(detector.detect("ride.TCX", b"<?xml"), TcxParser)
        assert isinstance(detector.detect("run.fit", b"\x10" + b"\x00" * 10), FitParser)

    def test_detects_fit_by_magic_bytes_regardless_of_extension(self) -> None:
        detector = build_default_detector()
        # Real FIT header: size 0x0E (14), protocol version 0x10, ".FIT" at
        # offset 8.
        header = bytes([0x0E, 0x10, 0, 0]) + b"\x00\x00\x00\x00" + b".FIT"
        assert isinstance(detector.detect("data.bin", header), FitParser)

    def test_rejects_unknown_format(self) -> None:
        detector = build_default_detector()
        with pytest.raises(ActivityImportError):
            detector.detect("notes.txt", b"hello world")


class TestResolveSport:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Running", "running"),
            ("Run Mode", "running"),
            ("Cycling", "cycling"),
            ("Indoor Rower", "rowing"),
            ("Yoga", "yoga"),
            ("handcycle", "other"),
            ("", None),
            (None, None),
        ],
    )
    def test_maps_vendor_labels(self, raw: str | None, expected: str | None) -> None:
        assert resolve_sport(raw) == expected


class TestGeo:
    def test_haversine_one_degree_of_latitude(self) -> None:
        assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111195.0, rel=1e-3)

    def test_distance_skips_points_without_coordinates(self) -> None:
        points = [
            ParsedTrackpoint(lat=0.0, lon=0.0),
            ParsedTrackpoint(lat=None, lon=None),
            ParsedTrackpoint(lat=0.001, lon=0.0),
        ]
        assert compute_distance_m(points) == pytest.approx(111.2, rel=1e-2)

    def test_distance_none_without_coordinates(self) -> None:
        assert compute_distance_m([ParsedTrackpoint(lat=None, lon=None)]) is None

    def test_elevation_gain_ignores_descents(self) -> None:
        points = [
            ParsedTrackpoint(altitude_m=100.0),
            ParsedTrackpoint(altitude_m=120.0),
            ParsedTrackpoint(altitude_m=110.0),
            ParsedTrackpoint(altitude_m=130.0),
        ]
        assert compute_elevation_gain_m(points) == pytest.approx(40.0)

    def test_elevation_gain_none_without_altitude(self) -> None:
        assert compute_elevation_gain_m([ParsedTrackpoint(altitude_m=None)]) is None


class TestTimeUtil:
    def test_parse_iso8601_zulu(self) -> None:
        assert parse_iso8601("2024-01-01T00:00:00Z") == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_parse_iso8601_offset_converted_to_utc(self) -> None:
        assert parse_iso8601("2024-01-01T02:00:00+02:00") == datetime(
            2024, 1, 1, 0, 0, 0, tzinfo=UTC
        )

    def test_parse_iso8601_invalid(self) -> None:
        assert parse_iso8601("not a time") is None
        assert parse_iso8601(None) is None

    def test_parse_iso_duration(self) -> None:
        assert parse_iso_duration_seconds("PT1H2M3S") == 3723
        assert parse_iso_duration_seconds("PT0S") == 0
        assert parse_iso_duration_seconds("PT30S") == 30
        assert parse_iso_duration_seconds("garbage") is None
        assert parse_iso_duration_seconds(None) is None
