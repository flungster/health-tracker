"""Activity trackpoint model: one row per recorded sample."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActivityTrackpoint(Base):
    """A single GPS/physiology sample of an activity.

    Bulk-loaded immutable data: intentionally no audit columns.
    """

    __tablename__ = "activity_trackpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"ActivityTrackpoint(activity_id={self.activity_id}, seq={self.seq})"
