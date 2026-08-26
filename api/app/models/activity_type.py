"""ORM model for the activity_types reference table."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActivityType(Base):
    """A canonical sport/activity type.

    Reference table: primary key is the value itself (the public API
    string), rows are seeded by migration and never updated or deleted, so
    there are no ``updated_at``/``deleted_at`` audit columns here.
    """

    __tablename__ = "activity_types"

    value: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"ActivityType(value={self.value!r})"
