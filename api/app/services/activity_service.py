"""Activity business logic: listing, detail, updates, deletion."""

import logging
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.activity_hr_zone_dao import ActivityHrZoneDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.imports import SPORT_TYPES
from app.models.activity import Activity
from app.models.activity_hr_zone import ActivityHrZone
from app.models.activity_split import ActivitySplit
from app.models.activity_trackpoint import ActivityTrackpoint
from app.models.cycling_activity import CyclingActivity
from app.models.rowing_activity import RowingActivity
from app.models.running_activity import RunningActivity
from app.models.strength_activity import StrengthActivity

logger = logging.getLogger(__name__)

ActivityDetail = tuple[
    Activity,
    list[ActivitySplit],
    ActivityHrZone | None,
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
        hr_zone_dao: ActivityHrZoneDao,
        running_dao: RunningActivityDao,
        cycling_dao: CyclingActivityDao,
        rowing_dao: RowingActivityDao,
        strength_dao: StrengthActivityDao,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._activity_dao = activity_dao
        self._trackpoint_dao = trackpoint_dao
        self._split_dao = split_dao
        self._hr_zone_dao = hr_zone_dao
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

        Raises NotFoundError when the activity is missing or not the
        caller's.
        """
        activity = self._require(user_id, activity_id)
        return (
            activity,
            self._split_dao.list_for_activity(activity_id),
            self._hr_zone_dao.get_for_activity(activity_id),
            self._running_dao.get_for_activity(activity_id),
            self._cycling_dao.get_for_activity(activity_id),
            self._rowing_dao.get_for_activity(activity_id),
            self._strength_dao.get_for_activity(activity_id),
        )

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
