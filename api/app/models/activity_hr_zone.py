"""Activity heart-rate zone model: time spent in each of the five zones."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class ActivityHrZone(IntIdModel, TimestampMixin):
    """Seconds spent in each heart-rate zone for one activity.

    Zones are percent-of-max-HR bands (see the migration comments).
    """

    __tablename__ = "activity_hr_zones"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False, unique=True
    )
    zone_1_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_2_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_3_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_4_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_5_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"ActivityHrZone(activity_id={self.activity_id})"
