"""Per-set detail for strength activities (manual entry, not file import)."""

from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdUuidModel


class StrengthExerciseSet(IntIdUuidModel):
    """One recorded set of one exercise within a strength activity.

    ``id`` is the internal integer primary key; ``uuid`` is the public
    identifier (sets are referenced by URL once manual entry lands).
    Immutable bulk detail rows: no audit columns by design.
    """

    __tablename__ = "strength_exercise_sets"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False
    )
    exercise_name: Mapped[str] = mapped_column(Text, nullable=False)
    set_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"StrengthExerciseSet(activity_id={self.activity_id}, set_index={self.set_index})"
