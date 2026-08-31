"""Activity business logic: listing, detail, updates, deletion."""

import logging
from datetime import date
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
from app.schemas.mappers.activity_zone_snapshot_mapper import ActivityZoneSnapshotMapper
from app.services.activity_stats import HrZoneStats
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

    def list_for_user(self, user_id: UUID, limit: int, offset: int) -> tuple[list[Activity], int]:
        """A page of the user's activities (newest first) plus the total."""
        activities = self._activity_dao.list_for_user(user_id, limit, offset)
        total = self._activity_dao.count_for_user(user_id)
        return activities, total

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
        """
        activity = self._require(user_id, activity_id)
        return (
            activity,
            self._split_dao.list_for_activity(activity_id),
            self._zones_for(user_id, activity_id),
            self._running_dao.get_for_activity(activity_id),
            self._cycling_dao.get_for_activity(activity_id),
            self._rowing_dao.get_for_activity(activity_id),
            self._strength_dao.get_for_activity(activity_id),
        )

    def _zones_for(self, user_id: UUID, activity_id: UUID) -> HrZoneStats | None:
        """The caller's view of the activity's zones.

        Resolves the caller's zone reference (custom > manual max HR > age;
        None when nothing is set — no fallback) and returns the seconds for it:
        from the live snapshot when that was computed against this same
        reference, otherwise recomputed from the trackpoints and stored as a
        fresh (superseding) snapshot. None also when there is no HR timeline.
        """
        profile = self._profile_dao.get(user_id)
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

    def get_trackpoints(self, user_id: UUID, activity_id: UUID) -> list[ActivityTrackpoint]:
        """All samples of the activity, in recorded order."""
        self._require(user_id, activity_id)
        return self._trackpoint_dao.list_for_activity(activity_id)

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
