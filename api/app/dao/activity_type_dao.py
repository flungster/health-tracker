"""DAO for the activity_types reference table (global, not user-scoped)."""

from sqlalchemy import select

from app.dao.base_dao import BaseDao
from app.models.activity_type import ActivityType


class ActivityTypeDao(BaseDao[ActivityType]):
    """Read access to the seeded sport type reference rows."""

    def list_all(self) -> list[ActivityType]:
        """Every sport type, in value order."""
        statement = select(ActivityType).order_by(ActivityType.value)
        return list(self.session.scalars(statement))
