"""Tests for ActivityStatistics fallback behavior.

Provider-fetched activities (Strava) may lack per-sample data; the summary
fields on ParsedActivity then serve as fallbacks. File parsers never set
those fields, so these tests pin the contract the provider path relies on.
"""

from datetime import UTC, datetime, timedelta

from app.imports.parsed import ParsedActivity, ParsedTrackpoint
from app.services.activity_stats import ActivityStatistics

START = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _point(
    seconds: int,
    *,
    lat: float = 52.3,
    lon: float = 4.9,
    heart_rate_bpm: int | None = None,
    cadence_rpm: int | None = None,
) -> ParsedTrackpoint:
    return ParsedTrackpoint(
        recorded_at=START + timedelta(seconds=seconds),
        lat=lat,
        lon=lon,
        heart_rate_bpm=heart_rate_bpm,
        cadence_rpm=cadence_rpm,
    )


class TestSummaryFallbacks:
    def test_hr_and_cadence_from_samples_win(self) -> None:
        parsed = ParsedActivity(
            sport_type="running",
            started_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            trackpoints=[_point(0, heart_rate_bpm=140, cadence_rpm=80)],
            heart_rate_avg_bpm=99,
            heart_rate_max_bpm=99,
            cadence_avg_rpm=11,
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.heart_rate_min_bpm == 140
        assert stats.heart_rate_avg_bpm == 140
        assert stats.heart_rate_max_bpm == 140
        assert stats.cadence_avg_rpm == 80

    def test_hr_falls_back_to_summary_fields_without_samples(self) -> None:
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            trackpoints=[],
            heart_rate_avg_bpm=143,
            heart_rate_max_bpm=165,
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.heart_rate_min_bpm is None
        assert stats.heart_rate_avg_bpm == 143
        assert stats.heart_rate_max_bpm == 165

    def test_cadence_falls_back_to_summary_field_without_samples(self) -> None:
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            trackpoints=[],
            cadence_avg_rpm=26,
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.cadence_avg_rpm == 26

    def test_no_samples_no_summary_stays_none(self) -> None:
        parsed = ParsedActivity(
            sport_type="strength",
            started_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            trackpoints=[],
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.heart_rate_avg_bpm is None
        assert stats.heart_rate_max_bpm is None
        assert stats.cadence_avg_rpm is None
