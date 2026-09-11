"""Data access for activity images."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdUuidDao
from app.models.activity_image import ActivityImage


class ActivityImageDao(IntIdUuidDao[ActivityImage]):
    """Reads/writes of the ``activity_images`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityImage)

    def add(self, image: ActivityImage) -> None:
        """Insert one row. The caller commits the session."""
        self.session.add(image)
        self.session.flush()

    def list_for_activity(self, activity_id: UUID) -> list[ActivityImage]:
        """An activity's live images in upload order (soft-deleted excluded)."""
        statement = (
            select(ActivityImage)
            .where(
                ActivityImage.activity_id == activity_id,
                ActivityImage.deleted_at.is_(None),
            )
            .order_by(ActivityImage.created_at.asc(), ActivityImage.id.asc())
        )
        return list(self.session.scalars(statement).unique().all())

    def soft_delete(self, image: ActivityImage) -> None:
        """Mark a row deleted. The caller commits the session."""
        statement = (
            update(ActivityImage).where(ActivityImage.id == image.id).values(deleted_at=func.now())
        )
        self.session.execute(statement)
