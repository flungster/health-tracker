"""Tests for the M11a DAOs: provider_credentials and server_settings.

These run against the migrated test database, so they also prove the
migration's constraints (unique provider, FK to providers) and triggers
(updated_at) behave as documented.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.dao.provider_credentials_dao import ProviderCredentialDao
from app.dao.server_setting_dao import ServerSettingDao
from app.models.provider_credential import ProviderCredential
from app.models.server_setting import ServerSetting
from app.security.secrets import SecretsBox


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


def _secret_box() -> SecretsBox:
    return SecretsBox(SecretsBox.generate_key())


@pytest.fixture(autouse=True)
def _clean_deployment_tables(engine: Engine) -> Iterator[None]:
    """Truncate the deployment-level tables these tests write to.

    They are not user-owned, so the ``client`` fixture's
    ``TRUNCATE ... CASCADE`` (which cascades from ``users``) never reaches
    them. These DAO tests use a direct session, not ``client``.
    """
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE provider_credentials, server_settings"))


class TestProviderCredentialDao:
    def test_empty_db_has_no_credentials(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            dao = ProviderCredentialDao(session)
            assert dao.get_active("strava") is None
            assert dao.get_any("strava") is None
            assert dao.mark_deleted("strava") is None  # no-op, no error

    def test_add_then_get_round_trip(self, engine: Engine) -> None:
        box = _secret_box()
        with _direct_session(engine) as session:
            dao = ProviderCredentialDao(session)
            dao.add(
                ProviderCredential(
                    provider="strava",
                    client_id="12345",
                    client_secret=box.encrypt("s3cret"),
                    display_name="Homelab Strava",
                )
            )
            session.commit()

            row = dao.get_active("strava")
            assert row is not None
            assert row.client_id == "12345"
            assert row.display_name == "Homelab Strava"
            assert box.decrypt(row.client_secret) == "s3cret"

            # The stored form is never the plaintext.
            assert "s3cret" not in row.client_secret

            by_id = dao.get_by_id(row.id)
            assert by_id is not None
            assert by_id.client_id == "12345"

    def test_soft_delete_hides_row_and_reconfigure_reuses_it(self, engine: Engine) -> None:
        box = _secret_box()
        with _direct_session(engine) as session:
            dao = ProviderCredentialDao(session)
            dao.add(
                ProviderCredential(
                    provider="strava",
                    client_id="11111",
                    client_secret=box.encrypt("first"),
                )
            )
            session.commit()

            dao.mark_deleted("strava")
            session.commit()
            assert dao.get_active("strava") is None

            # The row still exists (unique key spans deleted rows)...
            existing = dao.get_any("strava")
            assert existing is not None
            assert existing.deleted_at is not None
            assert existing.client_id == "11111"

            # ...so a reconfigure reuses it instead of inserting a twin.
            existing.client_id = "22222"
            existing.client_secret = box.encrypt("second")
            existing.display_name = "Relinked"
            existing.deleted_at = None
            dao.save(existing)
            session.commit()

            active = dao.get_active("strava")
            assert active is not None
            assert active.id == existing.id
            assert active.client_id == "22222"
            assert active.display_name == "Relinked"
            assert box.decrypt(active.client_secret) == "second"
            assert active.updated_at is not None
            assert active.updated_at >= active.created_at

            count = session.execute(
                select(func.count())
                .select_from(ProviderCredential)
                .where(ProviderCredential.provider == "strava")
            ).scalar_one()
            assert count == 1

    def test_unknown_provider_has_no_row(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            dao = ProviderCredentialDao(session)
            assert dao.get_active("garmin") is None  # not in the reference table either


class TestServerSettingDao:
    def test_key_round_trip(self, engine: Engine) -> None:
        key = SecretsBox.generate_key()
        with _direct_session(engine) as session:
            dao = ServerSettingDao(session)
            assert dao.get_by_key("secret_key") is None

            dao.add(ServerSetting(key="secret_key", value=key.decode()))
            session.commit()

            row = dao.get_by_key("secret_key")
            assert row is not None
            assert row.value == key.decode()
            assert dao.get_by_key("other") is None

    def test_update_replaces_the_value(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            dao = ServerSettingDao(session)
            dao.add(ServerSetting(key="secret_key", value="first"))
            session.commit()

            row = dao.get_by_key("secret_key")
            assert row is not None
            row.value = "second"
            dao.save(row)
            session.commit()

            reloaded = dao.get_by_key("secret_key")
            assert reloaded is not None
            assert reloaded.value == "second"
