"""Reads/writes of the ``activity_weather`` table (M24).

At most one live snapshot per activity (enforced by a partial unique index);
the read path is "get this activity's live row, if any". There is no update or
delete API — a snapshot lives until its activity does.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdUuidDao
from app.models.activity_weather import ActivityWeather


class ActivityWeatherDao(IntIdUuidDao[ActivityWeather]):
    """DAO for cached activity weather snapshots."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityWeather)

    def add(self, snapshot: ActivityWeather) -> None:
        """Insert one row. The caller commits the session."""
        self.session.add(snapshot)
        self.session.flush()

    def get_live_for_activity(self, activity_id: UUID) -> ActivityWeather | None:
        """The activity's live snapshot (soft-deleted rows excluded), if any."""
        statement = (
            sa.select(ActivityWeather)
            .where(
                ActivityWeather.activity_id == activity_id,
                ActivityWeather.deleted_at.is_(None),
            )
            .limit(1)
        )
        return self.session.scalars(statement).first()
