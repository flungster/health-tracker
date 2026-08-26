"""Strength-specific activity metrics."""

from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.sport_activity import SportActivityMixin


class StrengthActivity(Base, SportActivityMixin, TimestampMixin):
    """Summary metrics for activities with sport_type = strength."""

    __tablename__ = "strength_activity"

    total_sets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_exercises: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"StrengthActivity(activity_id={self.activity_id})"
