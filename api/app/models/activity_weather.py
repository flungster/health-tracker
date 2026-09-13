"""Activity weather model: one cached snapshot per activity (M24).

The hourly series lives in a standard-SQL ``json`` column — a display-only
blob the client reads whole. The row is immutable once written (no update
path), so ``fetched_at`` doubles as the snapshot's age. DDL (including the
json-array check) is owned by dbmate, like all schema here.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    Double,
    ForeignKey,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdUuidModel, TimestampMixin


class ActivityWeather(IntIdUuidModel, TimestampMixin):
    """A cached Open-Meteo weather snapshot for one activity."""

    __tablename__ = "activity_weather"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False
    )
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lon: Mapped[float] = mapped_column(Double, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    # Hourly snapshot: [{"time": "...", "temperature_c": ..., ...}, ...]
    data: Mapped[list[Any]] = mapped_column(sa.JSON, nullable=False)

    def __repr__(self) -> str:
        return f"ActivityWeather(activity_id={self.activity_id}, lat={self.lat}, lon={self.lon})"
