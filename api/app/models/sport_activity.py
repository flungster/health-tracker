"""Shared column for the 1:1 ``<sport>_activity`` metric tables."""

from uuid import UUID

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class SportActivityMixin:
    """Primary-key/foreign-key column linking a sport row to its activity.

    Every sport metric table has exactly one row per activity.
    """

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
