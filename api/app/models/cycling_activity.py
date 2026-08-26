"""Cycling-specific activity metrics."""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin
from app.models.sport_activity import SportActivityMixin


class CyclingActivity(IntIdModel, SportActivityMixin, TimestampMixin):
    """Power metrics for activities with sport_type = cycling."""

    __tablename__ = "cycling_activity"

    power_avg_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_max_w: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"CyclingActivity(activity_id={self.activity_id})"
