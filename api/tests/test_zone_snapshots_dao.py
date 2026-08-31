"""Tests for the M13a ``activity_zone_snapshots`` table and its DAO.

These run against the migrated test database, so they also prove the
migration's constraints (the partial unique index "at most one live snapshot
per activity", the FK to ``zone_sources``) and cascade behavior.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.dao.activity_dao import ActivityDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.activity_zone_snapshot_dao import ActivityZoneSnapshotDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.db.unit_of_work import UnitOfWork
from app.imports.base import FormatDetector
from app.imports.parsed import ParsedActivity
from app.models.activity_zone_snapshot import ActivityZoneSnapshot
from app.services.activity_stats import ActivityStatistics
from app.services.import_service import ImportService


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


@contextmanager
def _import_service(engine: Engine) -> Iterator[ImportService]:
    """An ImportService wired to a fresh session (closed on exit)."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    service = ImportService(
        unit_of_work=UnitOfWork(session),
        activity_dao=ActivityDao(session),
        trackpoint_dao=ActivityTrackpointDao(session),
        split_dao=ActivitySplitDao(session),
        running_dao=RunningActivityDao(session),
        cycling_dao=CyclingActivityDao(session),
        rowing_dao=RowingActivityDao(session),
        strength_dao=StrengthActivityDao(session),
        detector=FormatDetector([]),
        statistics=ActivityStatistics(),
        settings=get_settings(),
    )
    try:
        yield service
    finally:
        session.close()


def _user_uuid(register_user) -> UUID:
    return UUID(str(register_user()["user"]["id"]))


def _parsed_run() -> ParsedActivity:
    """A minimal parsed running activity (no trackpoints needed)."""
    return ParsedActivity(
        sport_type="running",
        name="Test Run",
        started_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        ended_at=datetime(2026, 8, 1, 9, 30, tzinfo=UTC),
        duration_seconds=1800,
        moving_seconds=1800,
        distance_m=5000.0,
        calories_kcal=350.0,
        elevation_gain_m=20.0,
    )


def _activity_uuid(client: TestClient, register_user, engine: Engine) -> UUID:
    """Import a minimal activity and return its public uuid."""
    user_uuid = _user_uuid(register_user)
    with _import_service(engine) as service:
        activity = service.import_parsed(user_uuid, _parsed_run(), source_format="gpx")
    return activity.uuid


def _snapshot(activity_id: UUID, **overrides) -> ActivityZoneSnapshot:
    values = {
        "activity_id": activity_id,
        "source": "max_heart_rate",
        "max_heart_rate": 180,
        "zone_1_seconds": 60,
        "zone_2_seconds": 300,
        "zone_3_seconds": 480,
        "zone_4_seconds": 600,
        "zone_5_seconds": 360,
    }
    values.update(overrides)
    return ActivityZoneSnapshot(**values)


class TestActivityZoneSnapshotDao:
    def test_get_current_none_without_snapshots(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            assert dao.get_current(activity_id) is None
            assert dao.get_current(uuid4()) is None

    def test_add_then_get_current_round_trip(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            saved = dao.add(_snapshot(activity_id))
            session.commit()

            current = ActivityZoneSnapshotDao(session).get_current(activity_id)
            assert current is not None
            assert current.id == saved.id
            assert current.source == "max_heart_rate"
            assert current.max_heart_rate == 180
            assert (current.zone_2_seconds, current.zone_5_seconds) == (300, 360)

    def test_second_live_snapshot_rejected(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        """The partial unique index allows at most one live row per activity."""
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            dao.add(_snapshot(activity_id))  # add() flushes, so this commits nothing yet
            session.commit()

            with pytest.raises(IntegrityError):
                dao.add(_snapshot(activity_id, source="age", age=42))

    def test_unknown_source_rejected_by_reference_fk(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            with pytest.raises(IntegrityError):
                dao.add(_snapshot(activity_id, source="bogus"))

    def test_supersede_soft_deletes_and_history_is_kept(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            first = dao.add(_snapshot(activity_id))
            session.commit()

            dao.mark_superseded(first)
            session.commit()

            # Hidden from the live read, but preserved for history.
            assert dao.get_current(activity_id) is None
            rows = (
                session.execute(
                    text("SELECT deleted_at FROM activity_zone_snapshots WHERE id = :id"),
                    {"id": first.id},
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0] is not None

    def test_new_snapshot_allowed_after_supersede(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        """The unique index is partial (live rows only), so superseding frees the slot."""
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            first = dao.add(_snapshot(activity_id))
            session.commit()

            dao.mark_superseded(first)
            second = dao.add(_snapshot(activity_id, source="age", age=42))  # no conflict
            session.commit()

            current = ActivityZoneSnapshotDao(session).get_current(activity_id)
            assert current is not None
            assert current.id == second.id

            total = session.execute(
                text("SELECT count(*) FROM activity_zone_snapshots WHERE activity_id = :a"),
                {"a": activity_id},
            ).scalar_one()
            assert total == 2  # the superseded row is kept, not destroyed

    def test_mark_superseded_is_noop_when_already_superseded(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            first = dao.add(_snapshot(activity_id))
            session.commit()

            dao.mark_superseded(first)
            session.commit()
            dao.mark_superseded(first)  # already soft-deleted: no error, no change
            session.commit()

            deleted = session.execute(
                text("SELECT count(*) FROM activity_zone_snapshots WHERE id = :id"),
                {"id": first.id},
            ).scalar_one()
            assert deleted == 1

    def test_snapshot_fields_match_source(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        """A custom-source snapshot stores the zone tops; a max-HR one does not."""
        activity_id = _activity_uuid(client, register_user, engine)
        with _direct_session(engine) as session:
            dao = ActivityZoneSnapshotDao(session)
            dao.add(
                _snapshot(
                    activity_id,
                    source="custom",
                    max_heart_rate=None,
                    custom_zone_1_top_bpm=120,
                    custom_zone_2_top_bpm=140,
                    custom_zone_3_top_bpm=160,
                    custom_zone_4_top_bpm=178,
                )
            )
            session.commit()

            current = ActivityZoneSnapshotDao(session).get_current(activity_id)
            assert current is not None
            assert (current.source, current.max_heart_rate) == ("custom", None)
            assert (
                current.custom_zone_1_top_bpm,
                current.custom_zone_4_top_bpm,
            ) == (120, 178)

    def test_activity_delete_cascades_snapshots(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service:
            activity = service.import_parsed(user_uuid, _parsed_run(), source_format="gpx")

        with _direct_session(engine) as session:
            snapshot_id = ActivityZoneSnapshotDao(session).add(_snapshot(activity.uuid)).id
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE uuid = :uuid"), {"uuid": user_uuid})

        with _direct_session(engine) as session:
            remaining = session.execute(
                text("SELECT count(*) FROM activity_zone_snapshots WHERE id = :id"),
                {"id": snapshot_id},
            ).scalar_one()
        assert remaining == 0
