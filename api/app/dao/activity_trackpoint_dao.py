"""Data access for activity trackpoints."""

from uuid import UUID

from sqlalchemy import ColumnElement, Float, Integer, case, func, select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.activity_trackpoint import ActivityTrackpoint
from app.services.activity_stats import HrZoneStats


class ActivityTrackpointDao(IntIdDao[ActivityTrackpoint]):
    """Bulk reads/writes of the ``activity_trackpoints`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ActivityTrackpoint)

    def add_all(self, trackpoints: list[ActivityTrackpoint]) -> None:
        """Insert a batch of trackpoints. The caller commits the session."""
        self.session.add_all(trackpoints)
        self.session.flush()

    def list_for_activity(self, activity_id: UUID) -> list[ActivityTrackpoint]:
        """All samples of an activity, in recorded order."""
        statement = (
            select(ActivityTrackpoint)
            .where(ActivityTrackpoint.activity_id == activity_id)
            .order_by(ActivityTrackpoint.seq)
        )
        return list(self.session.scalars(statement).unique().all())

    def zone_seconds_for(self, activity_id: UUID, max_heart_rate: int) -> HrZoneStats | None:
        """Seconds spent in each HR zone, relative to ``max_heart_rate``.

        Computed from the stored trackpoints at read time: a zone is relative
        to a *person* (the viewer's profile), so it must follow that profile
        rather than be frozen at import time. The bands are the
        percent-of-max-HR boundaries (below 56% / 56-63% / 64-71% / 72-80% /
        above 80%). Returns None when there is no HR timeline to distribute.
        """
        percent = ActivityTrackpoint.heart_rate_bpm.cast(Float) / max_heart_rate
        zone = case(
            (percent < 0.56, 1),
            (percent < 0.64, 2),
            (percent < 0.72, 3),
            (percent <= 0.80, 4),
            else_=5,
        ).label("zone")
        return self._aggregate_zone_seconds(activity_id, zone)

    def custom_zone_seconds_for(
        self, activity_id: UUID, tops: tuple[int, int, int, int]
    ) -> HrZoneStats | None:
        """Seconds spent in each HR zone, against user-defined custom tops.

        The zones are ``hr <= tops[0]``, ``(tops[0], tops[1]]`` and so on;
        zone 5 is everything above ``tops[3]``. The tops must be strictly
        ascending (the service enforces that when they are stored). Same
        per-sample timing rule as the percent bands; returns None when there
        is no HR timeline to distribute.
        """
        heart_rate = ActivityTrackpoint.heart_rate_bpm
        zone = case(
            (heart_rate <= tops[0], 1),
            (heart_rate <= tops[1], 2),
            (heart_rate <= tops[2], 3),
            (heart_rate <= tops[3], 4),
            else_=5,
        ).label("zone")
        return self._aggregate_zone_seconds(activity_id, zone)

    def _aggregate_zone_seconds(
        self, activity_id: UUID, zone: ColumnElement[int]
    ) -> HrZoneStats | None:
        """Distribute an activity's HR timeline over a per-sample ``zone``.

        Each timed, HR-bearing sample accounts for the time until the next
        such sample (the final sample has no following gap and contributes 0).
        Returns None when the activity carries no HR timeline at all.
        """
        recorded_at = ActivityTrackpoint.recorded_at
        next_recorded_at = func.lead(recorded_at).over(order_by=ActivityTrackpoint.seq)
        gap_seconds = func.extract("epoch", next_recorded_at - recorded_at).cast(Integer)
        subquery = (
            select(gap_seconds.label("gap_seconds"), zone)
            .where(ActivityTrackpoint.activity_id == activity_id)
            .where(recorded_at.is_not(None))
            .where(ActivityTrackpoint.heart_rate_bpm.is_not(None))
            .subquery()
        )
        statement = select(
            func.sum(subquery.c.gap_seconds).filter(subquery.c.zone == 1).label("zone_1_seconds"),
            func.sum(subquery.c.gap_seconds).filter(subquery.c.zone == 2).label("zone_2_seconds"),
            func.sum(subquery.c.gap_seconds).filter(subquery.c.zone == 3).label("zone_3_seconds"),
            func.sum(subquery.c.gap_seconds).filter(subquery.c.zone == 4).label("zone_4_seconds"),
            func.sum(subquery.c.gap_seconds).filter(subquery.c.zone == 5).label("zone_5_seconds"),
        )
        row = self.session.execute(statement).one()
        if all(value is None for value in row):
            return None
        return HrZoneStats(
            zone_1_seconds=int(row[0] or 0),
            zone_2_seconds=int(row[1] or 0),
            zone_3_seconds=int(row[2] or 0),
            zone_4_seconds=int(row[3] or 0),
            zone_5_seconds=int(row[4] or 0),
        )
