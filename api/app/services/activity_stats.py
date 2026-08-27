"""Pure statistics computed from a ParsedActivity at import time.

Everything the source file does not provide (splits, heart-rate zones,
summary values) is derived here from the raw trackpoints, so all formats
are treated identically. This module is pure: no DB, no HTTP.
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
    """Seconds spent in each of the five heart-rate zones."""

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
    hr_zones: HrZoneStats | None = None
    running_avg_pace_s_per_km: float | None = None
    running_min_pace_s_per_km: float | None = None
    running_max_pace_s_per_km: float | None = None
    cycling_power_avg_w: int | None = None
    cycling_power_max_w: int | None = None
    rowing_split_500m_seconds: float | None = None


class ActivityStatistics:
    """Derives splits, zones and summary metrics from trackpoints."""

    def compute(self, activity: ParsedActivity, max_heart_rate: int | None = None) -> ActivityStats:
        """Compute every derived statistic for a parsed activity.

        ``max_heart_rate`` is the user's configured max HR (zone reference);
        when absent the activity's own max HR is used.
        """
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

        zone_reference = max_heart_rate or stats.heart_rate_max_bpm
        if zone_reference:
            stats.hr_zones = self.compute_hr_zones(points, zone_reference)

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

    def compute_hr_zones(
        self, points: Sequence[ParsedTrackpoint], max_heart_rate: int
    ) -> HrZoneStats | None:
        """Distribute the activity's time across the five HR zones.

        Each sample accounts for the time until the next sample.
        """
        samples = [p for p in points if p.recorded_at is not None and p.heart_rate_bpm is not None]
        if len(samples) < 2 or max_heart_rate <= 0:
            return None
        zone_seconds = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for i in range(len(samples) - 1):
            current = samples[i]
            following = samples[i + 1]
            if current.recorded_at is None or following.recorded_at is None:
                continue
            if current.heart_rate_bpm is None:
                continue
            delta = int((following.recorded_at - current.recorded_at).total_seconds())
            if delta <= 0:
                continue
            zone_seconds[self._zone_for(current.heart_rate_bpm, max_heart_rate)] += delta
        if sum(zone_seconds.values()) <= 0:
            return None
        return HrZoneStats(
            zone_1_seconds=zone_seconds[1],
            zone_2_seconds=zone_seconds[2],
            zone_3_seconds=zone_seconds[3],
            zone_4_seconds=zone_seconds[4],
            zone_5_seconds=zone_seconds[5],
        )

    def _zone_for(self, heart_rate: int, max_heart_rate: int) -> int:
        """Percent-of-max-HR zone (56/64/72/80% boundaries)."""
        percent = heart_rate / max_heart_rate
        if percent < 0.56:
            return 1
        if percent < 0.64:
            return 2
        if percent < 0.72:
            return 3
        if percent <= 0.80:
            return 4
        return 5

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
