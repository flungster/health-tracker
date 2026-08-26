"""Activity split model: precomputed per-distance splits."""

from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ActivitySplit(Base, TimestampMixin):
    """A precomputed split (per km or per mile) of an activity.

    Computed from trackpoints at import time; ``pace_seconds`` is the pace
    in seconds per unit (km or mi) for that split.
    """

    __tablename__ = "activity_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    split_type: Mapped[str] = mapped_column(Text, nullable=False)
    split_index: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    pace_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    heart_rate_avg_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence_avg_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"ActivitySplit(activity_id={self.activity_id}, "
            f"split_type={self.split_type!r}, split_index={self.split_index})"
        )
