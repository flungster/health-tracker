"""Data access for strength exercise sets (manual entry)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdUuidDao
from app.models.strength_exercise_set import StrengthExerciseSet


class StrengthExerciseSetDao(IntIdUuidDao[StrengthExerciseSet]):
    """Reads and writes of the ``strength_exercise_sets`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, StrengthExerciseSet)

    def add(self, row: StrengthExerciseSet) -> StrengthExerciseSet:
        """Persist a set row. The caller commits the session."""
        self.session.add(row)
        self.session.flush()
        return row

    def list_for_activity(self, activity_uuid: UUID) -> list[StrengthExerciseSet]:
        """A strength activity's sets, in set order."""
        statement = (
            select(StrengthExerciseSet)
            .where(StrengthExerciseSet.activity_id == activity_uuid)
            .order_by(StrengthExerciseSet.set_index)
        )
        return list(self.session.scalars(statement).unique().all())
