"""Data access for activity trackpoints."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.activity_trackpoint import ActivityTrackpoint


class ActivityTrackpointDao(IntIdDao[ActivityTrackpoint]):
    """Bulk reads/writes of the ``activity_trackpoints`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityTrackpoint)

    def add_all(self, trackpoints: list[ActivityTrackpoint]) -> None:
        """Insert a batch of trackpoints. The caller commits the session."""
        self.session.add_all(trackpoints)
        self.session.flush()

    def list_for_activity(self, activity_id: UUID) -> list[ActivityTrackpoint]:
        """All samples of an activity, in recorded order."""
        statement = (
            select(ActivityTrackpoint)
            .where(ActivityTrackpoint.activity_id == activity_id)
            .order_by(ActivityTrackpoint.seq)
        )
        return list(self.session.scalars(statement).unique().all())
