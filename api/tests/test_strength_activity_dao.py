"""Tests for ``StrengthActivityDao.total_weight_for_period`` (M18 dashboard).

The weight sum cannot be exercised through the API: no import source sets
``total_weight_kg`` yet (file parsers carry no strength data and the Strava
non-elevated API does not expose it), so these seed rows directly against the
migrated test database and pin the summing rules — user scoping, the time
window, soft-deleted activities, and null-not-zero.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.dao.activity_dao import ActivityDao
from app.dao.sport_activity_dao import StrengthActivityDao
from app.models.activity import Activity
from app.models.strength_activity import StrengthActivity
from app.models.user import User

START = datetime(2024, 6, 1, tzinfo=UTC)


@contextmanager
def _direct_session(engine: Engine) -> Iterator[Session]:
    """A session outside the app's request lifecycle (closed on exit)."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _seed(
    engine: Engine,
    label: str,
    started_at: datetime | None = None,
    weight_kg: float | None = None,
    user: User | None = None,
) -> tuple[User, Activity]:
    """One strength activity (with its metric row), under an existing or new user.

    The metric row is always created — with a NULL weight when none is given,
    mirroring what the import path writes today. A fresh user is committed in
    its own session first: a user and an activity cannot be flushed together,
    because the FK targets ``users.uuid`` (a non-PK column) and SQLAlchemy's
    unit of work does not order such inserts. In the app, users always exist
    before any activity is imported anyway.
    """
    if user is None:
        with _direct_session(engine) as session:
            user = User(
                uuid=uuid4(),
                first_name="T",
                last_name=label,
                email=f"strength-{uuid4().hex[:12]}@example.com",
                password_hash="test-hash-not-argon2",
            )
            session.add(user)
            session.commit()

    with _direct_session(engine) as session:
        when = started_at or START
        activity = Activity(
            uuid=uuid4(),
            user_id=user.uuid,
            sport_type="strength",
            name=f"{label} session",
            started_at=when,
            ended_at=when.replace(hour=min(when.hour + 1, 23)),
            duration_seconds=3600,
        )
        session.add(activity)
        session.flush()
        session.add(StrengthActivity(activity_id=activity.uuid, total_weight_kg=weight_kg))
        session.commit()
    return user, activity


def test_sums_weights_in_range_for_one_user(engine: Engine) -> None:
    user, _ = _seed(engine, "a", START, 10.5)
    _, _ = _seed(engine, "a2", datetime(2024, 6, 3, tzinfo=UTC), 30.0, user=user)

    with _direct_session(engine) as session:
        dao = StrengthActivityDao(session)
        june = dao.total_weight_for_period(user.uuid, START, datetime(2024, 7, 1, tzinfo=UTC))
        july = dao.total_weight_for_period(
            user.uuid, datetime(2024, 7, 1, tzinfo=UTC), datetime(2024, 8, 1, tzinfo=UTC)
        )

    assert june == pytest.approx(40.5)
    # Same user, empty window -> null, not zero.
    assert july is None


def test_excludes_other_users_and_soft_deleted(engine: Engine) -> None:
    user_a, activity_a = _seed(engine, "a", START, 10.5)
    user_c, _ = _seed(engine, "c", START, 7.25)
    _, _ = _seed(engine, "b", datetime(2024, 8, 15, tzinfo=UTC), 99.0)

    with _direct_session(engine) as session:
        # Load a fresh instance in this session — the one from _seed is detached.
        activity = ActivityDao(session).get_by_uuid(activity_a.uuid)
        assert activity is not None
        activity.deleted_at = datetime(2024, 12, 31, tzinfo=UTC)
        session.commit()

    with _direct_session(engine) as session:
        dao = StrengthActivityDao(session)
        # User A's only weighted activity is soft-deleted -> null, not zero.
        assert (
            dao.total_weight_for_period(user_a.uuid, START, datetime(2024, 7, 1, tzinfo=UTC))
            is None
        )
        # User C's in-range weight counts; user B's row (other user, out of
        # window) never does.
        assert dao.total_weight_for_period(
            user_c.uuid, START, datetime(2024, 7, 1, tzinfo=UTC)
        ) == pytest.approx(7.25)


def test_null_when_no_weight_is_stored(engine: Engine) -> None:
    user, _ = _seed(engine, "empty", START, weight_kg=None)

    with _direct_session(engine) as session:
        total = StrengthActivityDao(session).total_weight_for_period(
            user.uuid, START, datetime(2024, 7, 1, tzinfo=UTC)
        )

    assert total is None


def test_unknown_user_is_null(engine: Engine) -> None:
    with _direct_session(engine) as session:
        total = StrengthActivityDao(session).total_weight_for_period(
            uuid4(), START, datetime(2024, 7, 1, tzinfo=UTC)
        )

    assert total is None
