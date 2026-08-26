"""Shared column for the 1:1 ``<sport>_activity`` metric tables."""

from uuid import UUID

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class SportActivityMixin:
    """Foreign-key column linking a sport row to its activity.

    Every sport metric table has exactly one row per activity. Concrete
    models also inherit ``IntIdModel`` for the int ``id`` primary key;
    ``activity_id`` is the unique public-uuid link.
    """

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False, unique=True
    )
