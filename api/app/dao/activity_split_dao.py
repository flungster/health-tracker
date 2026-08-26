"""Data access for activity splits."""

from uuid import UUID

from sqlalchemy import select

from app.dao.base_dao import BaseDao
from app.models.activity_split import ActivitySplit


class ActivitySplitDao(BaseDao[ActivitySplit]):
    """Reads/writes of the precomputed ``activity_splits`` table."""

    def add_all(self, splits: list[ActivitySplit]) -> None:
        """Insert a batch of splits. The caller commits the session."""
        self.session.add_all(splits)
        self.session.flush()

    def list_for_activity(self, activity_id: UUID) -> list[ActivitySplit]:
        """An activity's splits ordered by type (km before mi) and index."""
        statement = (
            select(ActivitySplit)
            .where(ActivitySplit.activity_id == activity_id)
            .order_by(ActivitySplit.split_type, ActivitySplit.split_index)
        )
        return list(self.session.scalars(statement).unique().all())
