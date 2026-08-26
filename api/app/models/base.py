"""Declarative base and shared column mixins for all ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Standard audit columns present on every table.

    ``created_at``/``updated_at`` defaults come from the database;
    ``updated_at`` is kept current by the ``set_updated_at`` trigger defined
    in the migrations. ``deleted_at`` implements soft deletion.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
