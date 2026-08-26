"""Sport type catalogue: read access to the reference table rows."""

from app.dao.activity_type_dao import ActivityTypeDao
from app.models.activity_type import ActivityType


class SportService:
    """Serves the canonical sport types (reference data, not user data)."""

    def __init__(self, activity_type_dao: ActivityTypeDao) -> None:
        self._activity_type_dao = activity_type_dao

    def list_types(self) -> list[ActivityType]:
        """Every sport type with its display description, in value order."""
        return self._activity_type_dao.list_all()
