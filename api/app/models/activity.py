"""Activity model: the main row for every imported activity."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Activity(Base, TimestampMixin):
    """An imported sport activity owned by a single user.

    Holds every metric that applies to most sports. Sport-specific metrics
    live in the 1:1 ``<sport>_activity`` tables.
    """

    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sport_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    moving_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    calories_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_min_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate_avg_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate_max_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence_avg_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_format: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"Activity(id={self.id}, sport_type={self.sport_type!r}, name={self.name!r})"
