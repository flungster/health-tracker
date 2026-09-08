"""Tests for the M14a ``user_profiles.imperial_units_enabled_at`` column.

These run against the migrated test database, so they also prove the
migration's shape (a nullable ``timestamptz`` on ``user_profiles``) and the
DAO round-trip: a stored instant persists, and clearing it returns to NULL.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.dao.user_profile_dao import UserProfileDao


@contextmanager
def _direct_session(engine: Engine) -> Iterator[Session]:
    """A session outside the app's request lifecycle.

    Always closed on exit, even when the test body fails — an open
    transaction would block the per-test TRUNCATE.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _empty_settings(**overrides: Any) -> dict[str, Any]:
    """Keyword arguments for apply_health_settings with one field overridden."""
    settings = {
        "max_heart_rate": None,
        "resting_heart_rate": None,
        "date_of_birth": None,
        "custom_zone_1_top_bpm": None,
        "custom_zone_2_top_bpm": None,
        "custom_zone_3_top_bpm": None,
        "custom_zone_4_top_bpm": None,
        "imperial_units_enabled_at": None,
    }
    settings.update(overrides)
    return settings


def test_imperial_units_timestamp_round_trips(engine: Engine, register_user: Any) -> None:
    """A stored enable instant persists; clearing it returns the column to NULL."""
    user_id = UUID(str(register_user()["user"]["id"]))

    instant = datetime(2026, 9, 5, 12, 30, tzinfo=UTC)
    with _direct_session(engine) as session:
        dao = UserProfileDao(session)

        profile = dao.apply_health_settings(
            user_id, **_empty_settings(imperial_units_enabled_at=instant)
        )
        session.commit()

        read_back = dao.get(user_id)
        assert read_back is not None  # the row was created by this write
        assert profile.imperial_units_enabled_at == instant
        assert read_back.imperial_units_enabled_at == instant

    with _direct_session(engine) as session:
        dao = UserProfileDao(session)
        cleared = dao.apply_health_settings(user_id, **_empty_settings())
        session.commit()

    assert cleared.imperial_units_enabled_at is None  # deliberate clear


def test_omitted_profile_keeps_metric_default(engine: Engine, register_user: Any) -> None:
    """A user without a profile row has no enable instant (metric by default)."""
    user_id = UUID(str(register_user()["user"]["id"]))

    with _direct_session(engine) as session:
        dao = UserProfileDao(session)
        assert dao.get(user_id) is None
