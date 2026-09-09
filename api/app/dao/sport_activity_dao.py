"""Data access for the 1:1 ``<sport>_activity`` metric tables.

A generic base DAO parameterized by the sport model class, with one thin
concrete DAO per sport table.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.base_dao import BaseDao
from app.models.activity import Activity
from app.models.cycling_activity import CyclingActivity
from app.models.rowing_activity import RowingActivity
from app.models.running_activity import RunningActivity
from app.models.sport_activity import SportActivityMixin
from app.models.strength_activity import StrengthActivity


class SportActivityDao[ModelT: SportActivityMixin](BaseDao[ModelT]):
    """Shared behaviour for the per-sport metric tables.

    ``ModelT`` is the ORM model of the concrete sport table (each has one
    row per activity). Sport rows are hidden through their activity: the
    activity lookup already filters soft-deleted rows.
    """

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        super().__init__(session, model)

    def add(self, row: ModelT) -> ModelT:
        """Persist a sport metric row. The caller commits the session."""
        self.session.add(row)
        self.session.flush()
        return row

    def get_for_activity(self, activity_id: UUID) -> ModelT | None:
        """The metric row for an activity, or None."""
        statement = select(self._model).where(self._model.activity_id == activity_id)
        return self.session.scalars(statement).unique().first()


class RunningActivityDao(SportActivityDao[RunningActivity]):
    """The ``running_activity`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, RunningActivity)


class CyclingActivityDao(SportActivityDao[CyclingActivity]):
    """The ``cycling_activity`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CyclingActivity)


class RowingActivityDao(SportActivityDao[RowingActivity]):
    """The ``rowing_activity`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, RowingActivity)


class StrengthActivityDao(SportActivityDao[StrengthActivity]):
    """The ``strength_activity`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, StrengthActivity)

    def total_weight_for_period(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> float | None:
        """Sum of total volume (kg) over the user's strength sessions in ``[start, end)``.

        Joins through ``activities`` for user scoping and the time window;
        soft-deleted activities are excluded there. NULL when no session in
        the range carries a weight (null-not-zero — see ``PeriodSummary``).
        """
        statement = (
            select(func.sum(StrengthActivity.total_weight_kg))
            .join(Activity, Activity.uuid == StrengthActivity.activity_id)
            .where(
                Activity.user_id == user_id,
                Activity.deleted_at.is_(None),
                StrengthActivity.total_weight_kg.is_not(None),
                Activity.started_at >= start,
                Activity.started_at < end,
            )
        )
        total = self.session.execute(statement).scalar_one()
        return None if total is None else float(total)
