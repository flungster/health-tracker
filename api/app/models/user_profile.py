"""Per-user health settings model (1:1 with users)."""

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class UserProfile(IntIdModel, TimestampMixin):
    """Health settings used to derive heart-rate zones and future estimates.

    Zone references (all optional; precedence custom > max_heart_rate > age):
      * ``custom_zone_*_top_bpm`` — user-defined zone boundaries (a complete,
        strictly-ascending set of four; NULL when not in use);
      * ``max_heart_rate`` — a manually entered max HR;
      * ``date_of_birth`` — the age-derived max HR is 220 - current_age.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.uuid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_zone_1_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_2_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_3_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_zone_4_top_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"UserProfile(user_id={self.user_id})"
