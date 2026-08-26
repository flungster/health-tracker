"""Data access for activities."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdUuidDao
from app.models.activity import Activity


class ActivityDao(IntIdUuidDao[Activity]):
    """Reads and writes of the ``activities`` table.

    Every lookup is scoped to a single user. Soft-deleted activities
    (``deleted_at IS NOT NULL``) are never returned.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, Activity)

    def add(self, activity: Activity) -> Activity:
        """Persist a new activity. The caller commits the session."""
        self.session.add(activity)
        self.session.flush()
        return activity

    def get_for_user(self, user_id: UUID, activity_uuid: UUID) -> Activity | None:
        """Fetch an active activity owned by ``user_id``, or None."""
        statement = select(Activity).where(
            Activity.uuid == activity_uuid,
            Activity.user_id == user_id,
            Activity.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def list_for_user(self, user_id: UUID, limit: int, offset: int) -> list[Activity]:
        """The user's active activities, newest first, with pagination."""
        statement = (
            select(Activity)
            .where(Activity.user_id == user_id, Activity.deleted_at.is_(None))
            .order_by(Activity.started_at.desc(), Activity.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement).unique().all())

    def count_for_user(self, user_id: UUID) -> int:
        """Number of the user's active activities (for pagination totals)."""
        statement = (
            select(func.count())
            .select_from(Activity)
            .where(Activity.user_id == user_id, Activity.deleted_at.is_(None))
        )
        return int(self.session.scalars(statement).one())

    def update(
        self,
        activity: Activity,
        name: str | None = None,
        description: str | None = None,
        sport_type: str | None = None,
    ) -> Activity:
        """Apply the provided changes; None values leave the field untouched."""
        if name is not None:
            activity.name = name
        if description is not None:
            activity.description = description
        if sport_type is not None:
            activity.sport_type = sport_type
        self.session.flush()
        return activity

    def soft_delete(self, activity: Activity) -> Activity:
        """Mark the activity as deleted (kept for history and rollback)."""
        statement = update(Activity).where(Activity.id == activity.id).values(deleted_at=func.now())
        self.session.execute(statement)
        self.session.flush()
        return activity
