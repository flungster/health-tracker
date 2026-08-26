"""Running-specific activity metrics."""

from sqlalchemy import Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin
from app.models.sport_activity import SportActivityMixin


class RunningActivity(IntIdModel, SportActivityMixin, TimestampMixin):
    """Pace metrics for activities with sport_type = running."""

    __tablename__ = "running_activity"

    avg_pace_s_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_pace_s_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_pace_s_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"RunningActivity(activity_id={self.activity_id})"
