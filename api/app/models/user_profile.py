"""Per-user health settings model (1:1 with users)."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class UserProfile(IntIdModel, TimestampMixin):
    """Health settings used to derive heart-rate zones and future estimates."""

    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.uuid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"UserProfile(user_id={self.user_id})"
