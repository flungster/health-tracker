"""Per-activity, versioned heart-rate zone results."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class ActivityZoneSnapshot(IntIdModel, TimestampMixin):
    """One heart-rate zone computation for an activity.

    A snapshot records the reference it was computed from (``source`` plus the
    corresponding values) and the resulting seconds per zone. At most one row
    per activity is live (``deleted_at IS NULL``, enforced by a partial unique
    index); when a newer computation supersedes one, the old row is soft-
    deleted and kept for history rather than destroyed.
    """

    __tablename__ = "activity_zone_snapshots"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False
    )

    # The reference this computation used (FK to zone_sources.value).
    source: Mapped[str] = mapped_column(ForeignKey("zone_sources.value"), nullable=False)

    # Reference values, populated per source (the rest stay NULL).
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_1_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_2_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_3_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_4_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resulting seconds per zone.
    zone_1_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_2_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_3_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_4_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone_5_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"ActivityZoneSnapshot(activity_id={self.activity_id}, source={self.source!r})"
