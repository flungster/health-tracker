"""Tests for ActivityStatistics fallback behavior.

Provider-fetched activities (Strava) may lack per-sample data; the summary
fields on ParsedActivity then serve as fallbacks. File parsers never set
those fields, so these tests pin the contract the provider path relies on.
"""

from datetime import UTC, datetime, timedelta

from app.imports.parsed import ParsedActivity, ParsedSportMetrics, ParsedTrackpoint
from app.services.activity_stats import (
    _DAILY_MAX_DAYS,
    ActivityStatistics,
    PeriodSummary,
    trend_buckets,
    zero_fill_trend,
)

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


class TestTrendBuckets:
    """Pure bucketing for the dashboard's distance-over-time trend."""

    def test_short_range_buckets_per_day_from_utc_midnight(self) -> None:
        start = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
        end = start + timedelta(days=3)

        bucket, starts = trend_buckets(start, end)

        assert bucket == "day"
        # First midnight is the UTC day containing start (before 07:00); the
        # last partial UTC day (Sep 4, up to 07:00) gets a bucket too.
        assert starts == [datetime(2026, 9, day, tzinfo=UTC) for day in (1, 2, 3, 4)]

    def test_daily_threshold_inclusive(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        assert trend_buckets(start, start + timedelta(days=_DAILY_MAX_DAYS))[0] == "day"
        assert (
            trend_buckets(start, start + timedelta(days=_DAILY_MAX_DAYS) + timedelta(hours=1))[0]
            == "month"
        )

    def test_year_range_buckets_per_month(self) -> None:
        start = datetime(2026, 1, 15, tzinfo=UTC)
        end = datetime(2027, 1, 1, tzinfo=UTC)

        bucket, starts = trend_buckets(start, end)

        assert bucket == "month"
        # Twelve firsts of months, starting with the month containing start.
        assert len(starts) == 12
        assert starts[0] == datetime(2026, 1, 1, tzinfo=UTC)
        assert starts[-1] == datetime(2026, 12, 1, tzinfo=UTC)

    def test_monthly_crosses_year_boundary(self) -> None:
        start = datetime(2026, 11, 3, tzinfo=UTC)
        end = datetime(2027, 4, 15, tzinfo=UTC)

        _, starts = trend_buckets(start, end)

        # Nov + Dec 2026 (from the 3rd), then Jan through April 2027.
        assert [s.year for s in starts] == [2026, 2026, 2027, 2027, 2027, 2027]
        assert [s.month for s in starts] == [11, 12, 1, 2, 3, 4]

    def test_zero_fill_keeps_order_and_fills_gaps(self) -> None:
        starts = [datetime(2026, 9, d, tzinfo=UTC) for d in (1, 2, 3)]
        raw = {starts[0]: 5.0, starts[2]: 1.5}

        points = zero_fill_trend(starts, raw)

        assert [p.distance_m for p in points] == [5.0, 0.0, 1.5]
        assert [p.start for p in points] == starts

    def test_zero_fill_empty_range(self) -> None:
        assert zero_fill_trend([], {}) == ()

    def test_period_summary_carries_nulls_not_zeros(self) -> None:
        summary = PeriodSummary(
            start=datetime(2026, 9, 1, tzinfo=UTC),
            end=datetime(2026, 9, 8, tzinfo=UTC),
            total_activities=1,
            by_sport_type={"strength": 1},
            moving_seconds_total=None,
            distance_m=None,
            elevation_gain_m=None,
            calories_kcal=120.0,
            avg_heart_rate_bpm=None,
            weight_lifted_kg=30.5,
            trend_points=(),  # no distance data at all -> empty series
        )

        assert summary.distance_m is None
        assert summary.trend_points == ()
