"""Tests for ActivityStatistics fallback behavior.

Provider-fetched activities (Strava) may lack per-sample data; the summary
fields on ParsedActivity then serve as fallbacks. File parsers never set
those fields, so these tests pin the contract the provider path relies on.
"""

from datetime import UTC, datetime, timedelta

from app.imports.parsed import ParsedActivity, ParsedSportMetrics, ParsedTrackpoint
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


class TestRowingStrokeRate:
    def test_per_sample_cadence_wins(self) -> None:
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=START,
            trackpoints=[_point(0, cadence_rpm=24), _point(30, cadence_rpm=26)],
            cadence_avg_rpm=11,  # summary value must be ignored when samples exist
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.rowing_stroke_rate_avg_spm == 25
        assert stats.rowing_stroke_rate_min_spm == 24
        assert stats.rowing_stroke_rate_max_spm == 26

    def test_explicit_parser_metrics_win_over_samples(self) -> None:
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=START,
            trackpoints=[_point(0, cadence_rpm=24)],
            sport_metrics=ParsedSportMetrics(stroke_rate_avg_spm=30),
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.rowing_stroke_rate_avg_spm == 30
        # No source provides min/max for an explicit average: they stay None.
        assert stats.rowing_stroke_rate_min_spm is None
        assert stats.rowing_stroke_rate_max_spm is None

    def test_falls_back_to_summary_cadence(self) -> None:
        # Strava reports a rower's stroke rate as the activity's average cadence.
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=START,
            trackpoints=[],
            cadence_avg_rpm=26,
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.rowing_stroke_rate_avg_spm == 26
        assert stats.rowing_stroke_rate_min_spm is None
        assert stats.rowing_stroke_rate_max_spm is None

    def test_no_source_records_strokes(self) -> None:
        parsed = ParsedActivity(
            sport_type="rowing",
            started_at=START,
            trackpoints=[],
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.rowing_stroke_rate_avg_spm is None
        assert stats.rowing_stroke_rate_min_spm is None
        assert stats.rowing_stroke_rate_max_spm is None

    def test_non_rowing_activity_has_no_stroke_rate(self) -> None:
        parsed = ParsedActivity(
            sport_type="running",
            started_at=START,
            trackpoints=[_point(0, cadence_rpm=170)],
        )
        stats = ActivityStatistics().compute(parsed)

        assert stats.rowing_stroke_rate_avg_spm is None
