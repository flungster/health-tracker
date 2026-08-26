"""Rowing-specific activity metrics."""

from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.sport_activity import SportActivityMixin


class RowingActivity(Base, SportActivityMixin, TimestampMixin):
    """Stroke metrics for activities with sport_type = rowing."""

    __tablename__ = "rowing_activity"

    stroke_rate_avg_spm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stroke_rate_min_spm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stroke_rate_max_spm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    split_500m_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"RowingActivity(activity_id={self.activity_id})"
