"""Activity image model: one row per photo attached to an activity."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdUuidModel, TimestampMixin


class ActivityImage(IntIdUuidModel, TimestampMixin):
    """An image attached to an activity.

    The file bytes live on disk under ``uploads/<user_id>/images/``; this row
    is the authoritative record (provenance, original filename, size). Soft
    delete: a deleted image keeps its row but is no longer served (its file is
    removed from disk).
    """

    __tablename__ = "activity_images"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.uuid", ondelete="CASCADE"), nullable=False
    )
    # Reference-table value (FK enforced in the schema, like Activity.sport_type).
    source: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    # On-disk file name under uploads/<user_id>/images/ (uuid + extension).
    stored_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"ActivityImage(activity_id={self.activity_id}, "
            f"source={self.source!r}, original_filename={self.original_filename!r})"
        )
