"""Activity business logic: listing, detail, updates, deletion."""

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.activity_zone_snapshot_dao import ActivityZoneSnapshotDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.imports import SPORT_TYPES
from app.models.activity import Activity
from app.models.activity_split import ActivitySplit
from app.models.activity_trackpoint import ActivityTrackpoint
from app.models.activity_zone_snapshot import ActivityZoneSnapshot
from app.models.cycling_activity import CyclingActivity
from app.models.rowing_activity import RowingActivity
from app.models.running_activity import RunningActivity
from app.models.strength_activity import StrengthActivity
from app.models.user_profile import UserProfile
from app.schemas.mappers.activity_zone_snapshot_mapper import ActivityZoneSnapshotMapper
from app.schemas.units import UnitSystem, units_for
from app.services.activity_stats import (
    HrZoneStats,
    PeriodSummary,
    SplitUnit,
    trend_buckets,
    zero_fill_trend,
)
from app.services.zone_reference import ZoneReference, ZoneSource, resolve_zone_reference

logger = logging.getLogger(__name__)

ActivityDetail = tuple[
    Activity,
    list[ActivitySplit],
    HrZoneStats | None,
    RunningActivity | None,
    CyclingActivity | None,
    RowingActivity | None,
    StrengthActivity | None,
    UnitSystem,  # the caller's display system; splits are already filtered to it
]


class ActivityService:
    """Reads and updates of a user's activities.

    Every method scopes by user first: activities that do not belong to the
    caller are indistinguishable from missing ones (404, not 403).
    """

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        activity_dao: ActivityDao,
        trackpoint_dao: ActivityTrackpointDao,
        split_dao: ActivitySplitDao,
        profile_dao: UserProfileDao,
        snapshot_dao: ActivityZoneSnapshotDao,
        running_dao: RunningActivityDao,
        cycling_dao: CyclingActivityDao,
        rowing_dao: RowingActivityDao,
        strength_dao: StrengthActivityDao,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._activity_dao = activity_dao
        self._trackpoint_dao = trackpoint_dao
        self._split_dao = split_dao
        self._profile_dao = profile_dao
        self._snapshot_dao = snapshot_dao
        self._running_dao = running_dao
        self._cycling_dao = cycling_dao
        self._rowing_dao = rowing_dao
        self._strength_dao = strength_dao

    def list_for_user(
        self, user_id: UUID, limit: int, offset: int
    ) -> tuple[list[Activity], int, UnitSystem]:
        """A page of the user's activities (newest first), plus the total and the
        caller's display unit system — unit-bearing view values are converted
        to it at mapping time (storage stays SI)."""
        activities = self._activity_dao.list_for_user(user_id, limit, offset)
        total = self._activity_dao.count_for_user(user_id)
        return activities, total, self._units_for(user_id)

    def period_summary(
        self, user_id: UUID, start_raw: str, end_raw: str
    ) -> tuple[PeriodSummary, UnitSystem]:
        """Dashboard aggregates over the user's activities in ``[start, end)``.

        ``start_raw`` / ``end_raw`` are ISO 8601 instants (naive = UTC); the
        range is half-open. The summary carries raw SI values plus the caller's
        display unit system — conversion happens in the mapper. Raises
        ValidationError on a malformed or inverted range.
        """
        start = self._parse_instant(start_raw, "start")
        end = self._parse_instant(end_raw, "end")
        if start >= end:
            raise ValidationError("'start' must be before 'end'", details=["inverted range"])

        bucket, starts = trend_buckets(start, end)
        total, moving_total, distance_m, elevation_gain_m, calories_kcal, avg_hr = (
            self._activity_dao.period_totals(user_id, start, end)
        )
        by_sport_type = dict(self._activity_dao.sport_counts_for_period(user_id, start, end))
        raw_trend = dict(self._activity_dao.distance_trend_for_period(user_id, start, end, bucket))
        # Empty series when the period has no distance data at all (the card is null too).
        trend_points = zero_fill_trend(starts, raw_trend) if distance_m is not None else ()

        return (
            PeriodSummary(
                start=start,
                end=end,
                total_activities=total,
                by_sport_type=by_sport_type,
                moving_seconds_total=moving_total,
                distance_m=distance_m,
                elevation_gain_m=elevation_gain_m,
                calories_kcal=calories_kcal,
                avg_heart_rate_bpm=None if avg_hr is None else int(round(avg_hr)),
                weight_lifted_kg=self._strength_dao.total_weight_for_period(user_id, start, end),
                trend_points=trend_points,
            ),
            self._units_for(user_id),
        )

    @staticmethod
    def _parse_instant(raw: str, param_name: str) -> datetime:
        """Parse an ISO 8601 instant; naive values are taken as UTC."""
        try:
            instant = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValidationError(
                f"'{param_name}' must be an ISO 8601 instant (e.g. 2024-06-01T09:00:00Z)"
            ) from exc
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        return instant

    def get_detail(self, user_id: UUID, activity_id: UUID) -> ActivityDetail:
        """An activity with all its derived rows.

        The heart-rate zones are computed at read time from the stored
        trackpoints, against the caller's zone reference — custom boundaries >
        manual max heart rate > age-derived (None when nothing is set) — so
        they always reflect the current profile. The result for a reference is
        kept as one live zone snapshot per activity: it is reused until the
        profile's reference changes, at which point a fresh computation
        supersedes it (the old row is kept for history). Raises NotFoundError
        when the activity is missing or not the caller's.

        Splits and unit-bearing values are presented in the caller's display
        unit system (the last tuple element): only that system's precomputed
        split rows are returned — km for metric, mi for imperial (an activity
        shorter than a tenth of one unit has none), and the mapper converts
        distance/elevation/pace/weight. Storage is never touched.
        """
        activity = self._require(user_id, activity_id)
        profile = self._profile_dao.get(user_id)
        units = units_for(profile.imperial_units_enabled_at if profile is not None else None)
        return (
            activity,
            self._splits_for(activity_id, units),
            self._zones_for(profile, activity_id),
            self._running_dao.get_for_activity(activity_id),
            self._cycling_dao.get_for_activity(activity_id),
            self._rowing_dao.get_for_activity(activity_id),
            self._strength_dao.get_for_activity(activity_id),
            units,
        )

    def _units_for(self, user_id: UUID) -> UnitSystem:
        """The caller's display unit system (metric when there is no profile)."""
        profile = self._profile_dao.get(user_id)
        return units_for(profile.imperial_units_enabled_at if profile is not None else None)

    def _splits_for(self, activity_id: UUID, units: UnitSystem) -> list[ActivitySplit]:
        """The precomputed splits of one system only (km for metric, mi otherwise)."""
        wanted = SplitUnit.MI if units is UnitSystem.IMPERIAL else SplitUnit.KM
        splits = self._split_dao.list_for_activity(activity_id)
        return [split for split in splits if split.split_type == wanted.value]

    def _zones_for(self, profile: UserProfile | None, activity_id: UUID) -> HrZoneStats | None:
        """The caller's view of the activity's zones.

        Resolves the caller's zone reference (custom > manual max HR > age;
        None when nothing is set — no fallback) and returns the seconds for it:
        from the live snapshot when that was computed against this same
        reference, otherwise recomputed from the trackpoints and stored as a
        fresh (superseding) snapshot. None also when there is no HR timeline.
        """
        reference = resolve_zone_reference(profile, date.today())
        if reference is None:
            return None

        current = self._snapshot_dao.get_current(activity_id)
        if current is not None and self._reference_matches(current, reference):
            return ActivityZoneSnapshotMapper.to_stats(current)

        stats = self._compute_zones(activity_id, reference)
        if stats is None:  # no HR timeline — nothing to snapshot or show
            return None

        self._store_snapshot(activity_id, current, reference, stats)
        logger.info(
            "Stored zone snapshot for activity %s (source=%s)", activity_id, reference.source.value
        )
        return stats

    def _compute_zones(self, activity_id: UUID, reference: ZoneReference) -> HrZoneStats | None:
        """Fresh zone seconds from the stored trackpoints, for a reference."""
        if reference.source is ZoneSource.CUSTOM and reference.custom_zone_tops is not None:
            return self._trackpoint_dao.custom_zone_seconds_for(
                activity_id, reference.custom_zone_tops
            )
        if reference.max_heart_rate is not None:
            return self._trackpoint_dao.zone_seconds_for(activity_id, reference.max_heart_rate)
        return None

    @staticmethod
    def _reference_matches(snapshot: ActivityZoneSnapshot, reference: ZoneReference) -> bool:
        """True when a stored snapshot was computed against exactly this reference.

        The bands are fully determined by the source plus its effective values
        (the custom tops, or the max heart rate for age/manual), so matching on
        those means a recompute would yield identical seconds.
        """
        if snapshot.source != reference.source.value:
            return False
        if reference.source is ZoneSource.CUSTOM and reference.custom_zone_tops is not None:
            stored = (
                snapshot.custom_zone_1_top_bpm,
                snapshot.custom_zone_2_top_bpm,
                snapshot.custom_zone_3_top_bpm,
                snapshot.custom_zone_4_top_bpm,
            )
            return stored == reference.custom_zone_tops
        return (
            reference.max_heart_rate is not None
            and snapshot.max_heart_rate == reference.max_heart_rate
        )

    def _store_snapshot(
        self,
        activity_id: UUID,
        current: ActivityZoneSnapshot | None,
        reference: ZoneReference,
        stats: HrZoneStats,
    ) -> None:
        """Record a fresh computation; supersede (keep for history) any live row."""
        if current is not None:
            self._snapshot_dao.mark_superseded(current)
        snapshot = ActivityZoneSnapshotMapper.create(activity_id, reference, stats)
        self._snapshot_dao.add(snapshot)
        self._unit_of_work.commit()

    def get_trackpoints(
        self, user_id: UUID, activity_id: UUID
    ) -> tuple[list[ActivityTrackpoint], UnitSystem]:
        """All samples of the activity, in recorded order — plus the caller's
        display unit system (altitude/speed are converted to it at mapping)."""
        self._require(user_id, activity_id)
        points = self._trackpoint_dao.list_for_activity(activity_id)
        return points, self._units_for(user_id)

    def update_for_user(
        self,
        user_id: UUID,
        activity_id: UUID,
        name: str | None = None,
        description: str | None = None,
        sport_type: str | None = None,
    ) -> Activity:
        """Apply the provided changes. Commits on success."""
        if sport_type is not None and sport_type not in SPORT_TYPES:
            raise ValidationError(
                f"Unknown sport type {sport_type!r}. Expected one of: {', '.join(SPORT_TYPES)}."
            )
        activity = self._require(user_id, activity_id)
        updated = self._activity_dao.update(
            activity, name=name, description=description, sport_type=sport_type
        )
        self._unit_of_work.commit()
        logger.info("Updated activity %s", activity_id)
        return updated

    def delete_for_user(self, user_id: UUID, activity_id: UUID) -> None:
        """Soft-delete the activity. Commits on success."""
        activity = self._require(user_id, activity_id)
        self._activity_dao.soft_delete(activity)
        self._unit_of_work.commit()
        logger.info("Deleted activity %s", activity_id)

    def _require(self, user_id: UUID, activity_id: UUID) -> Activity:
        activity = self._activity_dao.get_for_user(user_id, activity_id)
        if activity is None:
            raise NotFoundError("Activity not found.")
        return activity
