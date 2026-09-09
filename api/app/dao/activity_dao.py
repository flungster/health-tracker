"""Data access for activities."""

from datetime import UTC, datetime
from typing import Literal
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

    def period_totals(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> tuple[int, int | None, float | None, float | None, float | None, float | None]:
        """Dashboard aggregates over the user's active activities in ``[start, end)``.

        Returns ``(count, moving_seconds_total, distance_m, elevation_gain_m,
        calories_kcal, avg_heart_rate_bpm)``. ``count`` is always a number;
        each sum/average is NULL when no activity in the range carries that
        metric (null-not-zero — see ``PeriodSummary``). The heart-rate value is
        the simple mean of the per-activity average HRs.
        """
        statement = select(
            func.count().label("total"),
            func.sum(Activity.moving_seconds).label("moving_seconds_total"),
            func.sum(Activity.distance_m).label("distance_m"),
            func.sum(Activity.elevation_gain_m).label("elevation_gain_m"),
            func.sum(Activity.calories_kcal).label("calories_kcal"),
            func.avg(Activity.heart_rate_avg_bpm).label("avg_heart_rate_bpm"),
        ).where(
            Activity.user_id == user_id,
            Activity.deleted_at.is_(None),
            Activity.started_at >= start,
            Activity.started_at < end,
        )
        row = self.session.execute(statement).one()
        return (
            int(row.total),
            None if row.moving_seconds_total is None else int(row.moving_seconds_total),
            float(row.distance_m) if row.distance_m is not None else None,
            float(row.elevation_gain_m) if row.elevation_gain_m is not None else None,
            float(row.calories_kcal) if row.calories_kcal is not None else None,
            float(row.avg_heart_rate_bpm) if row.avg_heart_rate_bpm is not None else None,
        )

    def sport_counts_for_period(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> list[tuple[str, int]]:
        """(sport_type, activity count) pairs for the range — only sports with ≥ 1."""
        statement = (
            select(Activity.sport_type, func.count().label("n"))
            .where(
                Activity.user_id == user_id,
                Activity.deleted_at.is_(None),
                Activity.started_at >= start,
                Activity.started_at < end,
            )
            .group_by(Activity.sport_type)
        )
        return [(row.sport_type, int(row.n)) for row in self.session.execute(statement)]

    def distance_trend_for_period(
        self, user_id: UUID, start: datetime, end: datetime, bucket: Literal["day", "month"]
    ) -> list[tuple[datetime, float]]:
        """(bucket start in UTC, summed distance_m) for activities with a distance.

        Activities are assigned to buckets by their UTC calendar day/month
        (``timezone('UTC', started_at)``, then ``date_trunc``) — deterministic
        regardless of the database session's timezone. Buckets with no distance
        data are absent; zero-filling is the caller's job (``zero_fill_trend``).
        """
        bucket_start = func.date_trunc(bucket, func.timezone("UTC", Activity.started_at))
        statement = (
            select(bucket_start.label("bucket"), func.sum(Activity.distance_m).label("distance"))
            .where(
                Activity.user_id == user_id,
                Activity.deleted_at.is_(None),
                Activity.distance_m.is_not(None),
                Activity.started_at >= start,
                Activity.started_at < end,
            )
            .group_by(bucket_start)
            .order_by(bucket_start)
        )
        return [
            (row.bucket.replace(tzinfo=UTC), float(row.distance))
            for row in self.session.execute(statement)
        ]

    def exists_for_provider(self, provider: str, external_activity_id: str) -> bool:
        """Whether this provider activity was imported (by any user).

        Deliberately not user-scoped and not filtered on ``deleted_at``: it
        mirrors the global partial unique index on
        ``(provider, external_activity_id)``, which is the backstop the sync
        loop relies on (an external id imports at most once, full stop).
        """
        statement = select(Activity.id).where(
            Activity.provider == provider,
            Activity.external_activity_id == external_activity_id,
        )
        return self.session.scalars(statement).first() is not None

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
