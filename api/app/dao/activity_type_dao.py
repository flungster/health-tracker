"""DAO for the activity_types reference table (global, not user-scoped)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import BaseDao
from app.models.activity_type import ActivityType


class ActivityTypeDao(BaseDao[ActivityType]):
    """Read access to the seeded sport type reference rows."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityType)

    def list_all(self) -> list[ActivityType]:
        """Every sport type, in value order."""
        statement = select(ActivityType).order_by(ActivityType.value)
        return list(self.session.scalars(statement))
