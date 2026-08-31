"""ORM model for the zone_sources reference table."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ZoneSource(Base):
    """The reference a heart-rate zone snapshot was computed from.

    Reference table: primary key is the value itself (the public API string),
    rows are seeded by migration and never updated or deleted, so there are no
    ``updated_at``/``deleted_at`` audit columns here. (Distinct from the
    ``ZoneSource`` StrEnum in ``app.services.zone_reference``, which mirrors
    the same value set on the code side.)
    """

    __tablename__ = "zone_sources"

    value: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"ZoneSource(value={self.value!r})"
