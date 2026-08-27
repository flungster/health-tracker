"""ORM model for the providers reference table."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Provider(Base):
    """A known external data provider.

    Reference table: primary key is the value itself (the public API string,
    e.g. ``strava``), rows are seeded by migration and never updated or
    deleted, so there are no ``updated_at``/``deleted_at`` audit columns.
    (Distinct from the ``Provider`` StrEnum in ``app.providers.base``, which
    mirrors the same value set on the code side.)
    """

    __tablename__ = "providers"

    value: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"Provider(value={self.value!r})"
