"""Data access for per-activity heart-rate zone snapshots."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.activity_zone_snapshot import ActivityZoneSnapshot


class ActivityZoneSnapshotDao(IntIdDao[ActivityZoneSnapshot]):
    """Reads and writes of the ``activity_zone_snapshots`` table.

    A snapshot is a single zone computation for an activity. At most one row
    per activity is live (``deleted_at IS NULL``); superseding a snapshot soft-
    deletes the old row so its history is preserved.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityZoneSnapshot)

    def get_current(self, activity_id: UUID) -> ActivityZoneSnapshot | None:
        """The live (current) snapshot for an activity, or None when none."""
        statement = select(ActivityZoneSnapshot).where(
            ActivityZoneSnapshot.activity_id == activity_id,
            ActivityZoneSnapshot.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def add(self, snapshot: ActivityZoneSnapshot) -> ActivityZoneSnapshot:
        """Persist a new snapshot. The caller commits the session."""
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def mark_superseded(self, snapshot: ActivityZoneSnapshot) -> None:
        """Soft-delete a live snapshot because a newer one supersedes it."""
        statement = (
            update(ActivityZoneSnapshot)
            .where(
                ActivityZoneSnapshot.id == snapshot.id,
                ActivityZoneSnapshot.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        self.session.execute(statement)
