"""Pure statistics computed from a ParsedActivity at import time.

Everything the source file does not provide (splits, summary values) is
derived here from the raw trackpoints, so all formats are treated
identically. This module is pure: no DB, no HTTP.

Heart-rate zones are deliberately NOT computed here: a zone is relative to
the viewer's *zone reference* (custom boundaries, or a max heart rate that is
manual or age-derived — all profile settings), which can change after the
import, so zones are computed at view time from the stored trackpoints (see
``ActivityTrackpointDao.zone_seconds_for`` and ``custom_zone_seconds_for``)
instead of being frozen at import time.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.imports.geo import haversine_m
from app.imports.parsed import ParsedActivity, ParsedTrackpoint

KM_METERS = 1000.0
MILE_METERS = 1609.344


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

        return stats

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
