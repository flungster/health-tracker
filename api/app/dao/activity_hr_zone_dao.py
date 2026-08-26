"""Data access for activity heart-rate zones."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.activity_hr_zone import ActivityHrZone


class ActivityHrZoneDao(IntIdDao[ActivityHrZone]):
    """Reads/writes of the 1:1 ``activity_hr_zones`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityHrZone)

    def add(self, zone: ActivityHrZone) -> ActivityHrZone:
        """Persist a zone row. The caller commits the session."""
        self.session.add(zone)
        self.session.flush()
        return zone

    def get_for_activity(self, activity_id: UUID) -> ActivityHrZone | None:
        """The zone row for an activity, or None when not computed."""
        statement = select(ActivityHrZone).where(ActivityHrZone.activity_id == activity_id)
        return self.session.scalars(statement).unique().first()
