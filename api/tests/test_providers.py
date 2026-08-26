"""Tests for the provider foundation (M10a).

Covers the ``providers`` reference seed, the ``ProviderAccountDao``
(connection lifecycle + constraints), the activity provenance columns
(provider + external id + dedup index), the shared ``ImportService.import_parsed``
persistence path, and the ``ProviderRegistry``.
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
from app.dao.activity_hr_zone_dao import ActivityHrZoneDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.provider_account_dao import ProviderAccountDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import ActivityImportError, NotFoundError, ValidationError
from app.imports.base import FormatDetector
from app.imports.parsed import ParsedActivity
from app.models.provider_account import ProviderAccount
from app.providers import (
    ActivityIdPage,
    Provider,
    ProviderAdapter,
    ProviderCredentials,
    ProviderIdentity,
    ProviderRegistry,
)
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
        hr_zone_dao=ActivityHrZoneDao(session),
        running_dao=RunningActivityDao(session),
        cycling_dao=CyclingActivityDao(session),
        rowing_dao=RowingActivityDao(session),
        strength_dao=StrengthActivityDao(session),
        profile_dao=UserProfileDao(session),
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


class TestProviderReference:
    def test_seed_matches_provider_enum(self, engine: Engine) -> None:
        """The seeded ``providers`` rows mirror the code-side ``Provider`` enum."""
        with _direct_session(engine) as session:
            values = session.execute(text("SELECT value FROM providers")).scalars().all()
        assert sorted(values) == sorted(member.value for member in Provider)


class TestProviderAccountDao:
    def _make_account(self, user_uuid: UUID) -> ProviderAccount:
        return ProviderAccount(
            user_id=user_uuid,
            provider="strava",
            external_user_id="12345",
            display_name="Alice Doe",
            refresh_token="refresh-secret",
            access_token="access-secret",
            token_expires_at=datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
            scope="activity:read_all",
        )

    def test_add_and_get_for_user(self, client: TestClient, register_user, engine: Engine) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            account = ProviderAccountDao(session).add(self._make_account(user_uuid))
            session.commit()

            fetched = ProviderAccountDao(session).get_for_user(user_uuid, "strava")
            assert fetched is not None
            assert fetched.id == account.id
            assert fetched.external_user_id == "12345"
            assert fetched.sync_cursor is None
            assert fetched.last_sync_at is None

            assert ProviderAccountDao(session).get_for_user(user_uuid, "garmin") is None
            assert ProviderAccountDao(session).get_for_user(uuid4(), "strava") is None

    def test_get_by_id(self, client: TestClient, register_user, engine: Engine) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            account = ProviderAccountDao(session).add(self._make_account(user_uuid))
            session.commit()
            dao = ProviderAccountDao(session)

            by_id = dao.get_by_id(account.id)
            assert by_id is not None
            assert by_id.user_id == user_uuid
            assert dao.get_by_id(999_999) is None

    def test_one_row_per_user_per_provider(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            dao = ProviderAccountDao(session)
            dao.add(self._make_account(user_uuid))
            session.commit()
            with pytest.raises(IntegrityError):
                dao.add(self._make_account(user_uuid))  # add() flushes

    def test_mark_deleted_soft_deletes_and_hides(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            account = ProviderAccountDao(session).add(self._make_account(user_uuid))
            session.commit()

            ProviderAccountDao(session).mark_deleted(user_uuid, "strava")
            session.commit()

            assert ProviderAccountDao(session).get_for_user(user_uuid, "strava") is None
            row = session.get(ProviderAccount, account.id)
            assert row is not None
            assert row.deleted_at is not None

    def test_disconnecting_without_a_connection_is_a_noop(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            ProviderAccountDao(session).mark_deleted(user_uuid, "strava")
            session.commit()  # no rows: no error

    def test_user_cascade_deletes_accounts(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _direct_session(engine) as session:
            account = ProviderAccountDao(session).add(self._make_account(user_uuid))
            session.commit()

            session.execute(text("DELETE FROM users WHERE uuid = :uuid"), {"uuid": user_uuid})
            session.commit()

            remaining = session.execute(
                text("SELECT count(*) FROM provider_accounts WHERE id = :id"),
                {"id": account.id},
            ).scalar_one()
            assert remaining == 0


class TestActivityProvenance:
    def test_import_parsed_stores_provider_provenance(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service:
            activity = service.import_parsed(
                user_uuid,
                _parsed_run(),
                provider="strava",
                external_activity_id="987654321",
            )
            assert activity.provider == "strava"
            assert activity.external_activity_id == "987654321"
            assert activity.source_format is None
            assert activity.original_filename is None
            assert activity.file_path is None

    def test_import_parsed_keeps_file_provenance(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service:
            activity = service.import_parsed(
                user_uuid,
                _parsed_run(),
                source_format="gpx",
                original_filename="run.gpx",
                file_path="/tmp/uploads/x.gpx",
            )
            assert activity.source_format == "gpx"
            assert activity.provider is None
            assert activity.external_activity_id is None

    def test_file_imports_with_null_provenance_do_not_collide(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        """NULL (provider, external_activity_id) rows never hit the dedup index."""
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service:
            service.import_parsed(user_uuid, _parsed_run(), source_format="gpx")
            service.import_parsed(user_uuid, _parsed_run(), source_format="tcx")

    def test_duplicate_provider_external_id_rejected(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service:
            service.import_parsed(
                user_uuid, _parsed_run(), provider="strava", external_activity_id="111"
            )
            with pytest.raises(IntegrityError):
                service.import_parsed(
                    user_uuid, _parsed_run(), provider="strava", external_activity_id="111"
                )

    def test_import_parsed_rejects_unknown_provider(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service, pytest.raises(ValidationError):
            service.import_parsed(user_uuid, _parsed_run(), provider="garmin")

    def test_import_parsed_rejects_activity_without_timestamps(
        self, client: TestClient, register_user, engine: Engine
    ) -> None:
        user_uuid = _user_uuid(register_user)
        with _import_service(engine) as service, pytest.raises(ActivityImportError):
            service.import_parsed(user_uuid, ParsedActivity(sport_type="running"))


class TestProviderRegistry:
    def _stub(self, name: str) -> ProviderAdapter:
        class _Stub(ProviderAdapter):
            def authorize_url(self, state: str) -> str:
                return f"https://{name}.example.com/authorize?state={state}"

            def exchange_code(self, code: str) -> ProviderCredentials:
                raise NotImplementedError

            def refresh(self, credentials: ProviderCredentials) -> ProviderCredentials:
                raise NotImplementedError

            def fetch_identity(self, access_token: str) -> ProviderIdentity:
                raise NotImplementedError

            def fetch_activity_ids(self, access_token: str, cursor: str | None) -> ActivityIdPage:
                raise NotImplementedError

            def fetch_activity(
                self, access_token: str, external_activity_id: str
            ) -> ParsedActivity:
                raise NotImplementedError

            def revoke(self, credentials: ProviderCredentials) -> None:
                raise NotImplementedError

        # Class bodies can't close over the enclosing scope, so assign the
        # ClassVar from outside.
        _Stub.provider = name
        return _Stub()

    def test_register_get_and_available(self) -> None:
        registry = ProviderRegistry()
        strava = self._stub("strava")
        registry.register(strava)

        assert registry.get("strava") is strava
        assert registry.available() == ["strava"]

    def test_unknown_provider_raises_not_found(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(NotFoundError):
            registry.get("garmin")
        assert registry.available() == []

    def test_duplicate_provider_registration_rejected(self) -> None:
        registry = ProviderRegistry()
        registry.register(self._stub("strava"))
        with pytest.raises(NotFoundError):
            registry.register(self._stub("strava"))
