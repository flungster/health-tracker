"""Pure statistics for activities: import-time and view-time.

Everything the source file does not provide (splits, summary values) is
derived here from the raw trackpoints at import time, so all formats are
treated identically. The module also holds the pure types and helpers for
the view-time period summary (dashboard): bucketing, zero-fill and the raw
summary dataclass. This module is pure: no DB, no HTTP.

Heart-rate zones are deliberately NOT computed here: a zone is relative to
the viewer's *zone reference* (custom boundaries, or a max heart rate that is
manual or age-derived — all profile settings), which can change after the
import, so zones are computed at view time from the stored trackpoints (see
``ActivityTrackpointDao.zone_seconds_for`` and ``custom_zone_seconds_for``)
instead of being frozen at import time.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Literal

from app.imports.geo import haversine_m
from app.imports.parsed import ParsedActivity, ParsedTrackpoint

KM_METERS = 1000.0
MILE_METERS = 1609.344


# Ranges up to this length bucket per day; longer ones (the year view) bucket
# per month, so the trend stays a readable number of points. Week and month
# periods are at most ~6 weeks; a year needs months, not 365 daily points.
_DAILY_MAX_DAYS = 62


@dataclass(frozen=True)
class TrendPoint:
    """One raw (SI, meters) bucket of the distance-over-time trend.

    ``start`` is the UTC instant that begins the bucket (a midnight for day
    buckets, a first-of-month 00:00 UTC for month buckets). Buckets with no
    activity carry ``distance_m == 0.0`` — the series is zero-filled so the
    chart axis stays continuous (see ``zero_fill_trend``).
    """

    start: datetime
    distance_m: float


@dataclass(frozen=True)
class PeriodSummary:
    """Raw (SI) aggregates for one user's activities over ``[start, end)``.

    Built by the service from DAO rows; unit-bearing values are converted to
    the caller's display system in ``ActivityMapper.to_period_summary_view``.
    A metric with no contributing data is None, never zero ("no elevation
    recorded" != "zero climbed"). ``trend_points`` is empty when the period
    has no distance data at all; otherwise it covers every bucket in the range.

    ``avg_heart_rate_bpm`` is the simple mean of the per-activity average HRs
    (over activities that have one), rounded to a whole bpm. ``weight_lifted_kg``
    is the summed total volume of the period's strength sessions; no import
    source provides weights yet, so it is None until one does.
    """

    start: datetime
    end: datetime
    total_activities: int
    by_sport_type: dict[str, int]
    moving_seconds_total: int | None
    distance_m: float | None
    elevation_gain_m: float | None
    calories_kcal: float | None
    avg_heart_rate_bpm: int | None
    weight_lifted_kg: float | None
    trend_points: tuple[TrendPoint, ...]


def trend_buckets(start: datetime, end: datetime) -> tuple[Literal["day", "month"], list[datetime]]:
    """The trend's bucket starts covering ``[start, end)``, in UTC.

    Returns ``(granularity, starts)``: day buckets (midnights) for ranges of
    at most ``_DAILY_MAX_DAYS`` days, month buckets (firsts of months 00:00
    UTC) beyond that. The first bucket may begin before ``start`` — it is the
    calendar day/month containing ``start``, matching how activities are
    assigned to buckets (by their UTC date). Buckets with no activity are the
    caller's concern (``zero_fill_trend``).

    Note: buckets follow UTC calendar days/months; for a user whose local day
    differs from UTC, an activity near its midnight boundary may land in the
    neighbouring bucket. User-localized boundaries belong to the (parked)
    user-timezone work, like the feed's day grouping.
    """
    starts: list[datetime] = []
    if (end - start) <= timedelta(days=_DAILY_MAX_DAYS):
        day = date(start.year, start.month, start.day)  # UTC calendar date of start
        while True:
            bucket_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
            if bucket_start >= end:
                break
            starts.append(bucket_start)
            day += timedelta(days=1)
        return "day", starts

    year, month = start.year, start.month
    while True:
        first_of_month = datetime(year, month, 1, tzinfo=UTC)
        if first_of_month >= end:
            break
        starts.append(first_of_month)
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return "month", starts


def zero_fill_trend(
    bucket_starts: list[datetime], raw_distances_m: Mapping[datetime, float]
) -> tuple[TrendPoint, ...]:
    """Join the aggregated per-bucket distances onto every bucket start.

    Buckets without an activity (or with none that has a distance) become
    0.0, so the returned series is continuous across ``bucket_starts``.
    """
    return tuple(
        TrendPoint(start=start, distance_m=raw_distances_m.get(start, 0.0))
        for start in bucket_starts
    )


class SplitUnit(StrEnum):
    """Distance units splits are precomputed in.

    Values mirror the seeded rows of the ``split_units`` reference table
    (the schema-level source of truth, enforced by
    ``activity_splits_split_type_fkey``).
    """

    KM = "km"
    MI = "mi"


@dataclass
class SplitStats:
    """One computed per-distance split."""

    split_type: SplitUnit
    split_index: int
    duration_seconds: int
    pace_seconds: float
    heart_rate_avg_bpm: int | None = None
    cadence_avg_rpm: int | None = None


@dataclass
class HrZoneStats:
    """Seconds spent in each of the five heart-rate zones.

    Computed at view time against the viewer's zone reference (custom
    boundaries > manual max heart rate > age-derived), not at import time —
    see the module docstring. The result is kept as a versioned per-activity
    snapshot, superseded when the reference changes.
    """

    zone_1_seconds: int = 0
    zone_2_seconds: int = 0
    zone_3_seconds: int = 0
    zone_4_seconds: int = 0
    zone_5_seconds: int = 0


@dataclass
class ActivityStats:
    """All derived statistics for one imported activity."""

    heart_rate_min_bpm: int | None = None
    heart_rate_avg_bpm: int | None = None
    heart_rate_max_bpm: int | None = None
    cadence_avg_rpm: int | None = None
    splits: list[SplitStats] = field(default_factory=list)
    running_avg_pace_s_per_km: float | None = None
    running_min_pace_s_per_km: float | None = None
    running_max_pace_s_per_km: float | None = None
    cycling_power_avg_w: int | None = None
    cycling_power_max_w: int | None = None
    rowing_split_500m_seconds: float | None = None
    rowing_stroke_rate_avg_spm: int | None = None
    rowing_stroke_rate_min_spm: int | None = None
    rowing_stroke_rate_max_spm: int | None = None


class ActivityStatistics:
    """Derives splits, zones and summary metrics from trackpoints."""

    def compute(self, activity: ParsedActivity) -> ActivityStats:
        """Compute every derived statistic for a parsed activity."""
        points = activity.trackpoints
        stats = ActivityStats()

        heart_rates = [p.heart_rate_bpm for p in points if p.heart_rate_bpm]
        if heart_rates:
            stats.heart_rate_min_bpm = min(heart_rates)
            stats.heart_rate_avg_bpm = round(sum(heart_rates) / len(heart_rates))
            stats.heart_rate_max_bpm = max(heart_rates)
        else:
            stats.heart_rate_avg_bpm = activity.heart_rate_avg_bpm
            stats.heart_rate_max_bpm = activity.heart_rate_max_bpm

        cadences = [p.cadence_rpm for p in points if p.cadence_rpm]
        if cadences:
            stats.cadence_avg_rpm = round(sum(cadences) / len(cadences))
        else:
            stats.cadence_avg_rpm = activity.cadence_avg_rpm

        stats.splits = self.compute_splits(points, SplitUnit.KM, KM_METERS)
        stats.splits.extend(self.compute_splits(points, SplitUnit.MI, MILE_METERS))

        stats.running_avg_pace_s_per_km = self._overall_pace(activity)
        km_paces = [s.pace_seconds for s in stats.splits if s.split_type == SplitUnit.KM]
        if km_paces:
            stats.running_min_pace_s_per_km = min(km_paces)
            stats.running_max_pace_s_per_km = max(km_paces)

        if activity.sport_type == "cycling":
            power = [p.power_w for p in points if p.power_w]
            if power:
                stats.cycling_power_avg_w = round(sum(power) / len(power))
                stats.cycling_power_max_w = max(power)
            else:
                stats.cycling_power_avg_w = activity.sport_metrics.power_avg_w
                stats.cycling_power_max_w = activity.sport_metrics.power_max_w

        if activity.sport_type == "rowing":
            stats.rowing_split_500m_seconds = self._rowing_500m(activity)
            self._compute_rowing_stroke_rate(stats, activity, points)

        return stats

    def _compute_rowing_stroke_rate(
        self, stats: ActivityStats, activity: ParsedActivity, points: Sequence[ParsedTrackpoint]
    ) -> None:
        """Derive the rowing stroke rate (strokes per minute).

        Precedence: an explicit parser-provided value, then the per-sample
        cadence (rowing devices export their stroke rate in the record's
        "cadence" field), then the summary-level cadence (Strava reports a
        rower's stroke rate as its average cadence). All three stay None when
        the source recorded no strokes at all.
        """
        metrics = activity.sport_metrics
        if metrics.stroke_rate_avg_spm is not None:
            stats.rowing_stroke_rate_avg_spm = metrics.stroke_rate_avg_spm
            stats.rowing_stroke_rate_min_spm = metrics.stroke_rate_min_spm
            stats.rowing_stroke_rate_max_spm = metrics.stroke_rate_max_spm
            return

        strokes = [p.cadence_rpm for p in points if p.cadence_rpm]
        if strokes:
            stats.rowing_stroke_rate_avg_spm = round(sum(strokes) / len(strokes))
            stats.rowing_stroke_rate_min_spm = min(strokes)
            stats.rowing_stroke_rate_max_spm = max(strokes)
            return

        # Summary fallback (Strava's "average cadence" for rowing).
        stats.rowing_stroke_rate_avg_spm = activity.cadence_avg_rpm

    def compute_splits(
        self, points: Sequence[ParsedTrackpoint], split_type: SplitUnit, unit_m: float
    ) -> list[SplitStats]:
        """Group samples into per-unit splits (km or mile) and time them."""
        series = self._distance_series(points)
        if len(series) < 2:
            return []
        if series[-1][1] < unit_m * 0.1:
            return []

        groups: dict[int, list[ParsedTrackpoint]] = {}
        for _t, d, point in series:
            groups.setdefault(int(d // unit_m), []).append(point)

        splits: list[SplitStats] = []
        sorted_indexes = sorted(groups)
        last_index = sorted_indexes[-1]
        for position, index in enumerate(sorted_indexes):
            samples = groups[index]
            if len(samples) < 2:
                continue
            start_time = samples[0].recorded_at
            if start_time is None:
                continue
            end_time = samples[-1].recorded_at
            if index < last_index:
                next_samples = groups[sorted_indexes[position + 1]]
                end_time = next_samples[0].recorded_at
            if end_time is None:
                continue

            duration = max(0, int((end_time - start_time).total_seconds()))
            if index < last_index:
                covered_m = unit_m
            else:
                covered_m = max(0.0, series[-1][1] - index * unit_m)
                if covered_m < unit_m * 0.1:
                    continue
            pace = duration / (covered_m / unit_m)

            heart_rates = [p.heart_rate_bpm for p in samples if p.heart_rate_bpm]
            cadences = [p.cadence_rpm for p in samples if p.cadence_rpm]
            splits.append(
                SplitStats(
                    split_type=split_type,
                    split_index=index + 1,
                    duration_seconds=duration,
                    pace_seconds=round(pace, 1),
                    heart_rate_avg_bpm=(
                        round(sum(heart_rates) / len(heart_rates)) if heart_rates else None
                    ),
                    cadence_avg_rpm=(round(sum(cadences) / len(cadences)) if cadences else None),
                )
            )
        return splits

    def _distance_series(
        self, points: Sequence[ParsedTrackpoint]
    ) -> list[tuple[object, float, ParsedTrackpoint]]:
        """(time, cumulative_meters, point) for every timed, positioned sample."""
        series: list[tuple[object, float, ParsedTrackpoint]] = []
        cumulative = 0.0
        previous: tuple[float, float] | None = None
        for point in points:
            if point.recorded_at is None or point.lat is None or point.lon is None:
                continue
            if previous is not None:
                cumulative += haversine_m(previous[0], previous[1], point.lat, point.lon)
            series.append((point.recorded_at, cumulative, point))
            previous = (point.lat, point.lon)
        return series

    def _overall_pace(self, activity: ParsedActivity) -> float | None:
        """Average pace in seconds per km over the whole activity."""
        moving = activity.moving_seconds or activity.duration_seconds
        if not moving or not activity.distance_m or activity.distance_m <= 0:
            return None
        return round(moving / (activity.distance_m / KM_METERS), 1)

    def _rowing_500m(self, activity: ParsedActivity) -> float | None:
        """Average 500 m split in seconds (the standard rowing pace)."""
        moving = activity.moving_seconds or activity.duration_seconds
        if not moving or not activity.distance_m or activity.distance_m <= 0:
            return None
        return round(moving / (activity.distance_m / 500.0), 1)
