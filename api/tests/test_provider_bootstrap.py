"""M11b: startup bootstrap — Fernet key get-or-generate and the provider
registry built from ``provider_credentials`` (the database is the only
source of credentials).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.dao.provider_credentials_dao import ProviderCredentialDao
from app.dao.server_setting_dao import ServerSettingDao
from app.models.provider_credential import ProviderCredential
from app.models.server_setting import ServerSetting
from app.providers.factory import build_provider_registry
from app.providers.registry import ProviderRegistry
from app.security.secrets import SECRET_KEY_SETTING, SecretsBox, ensure_secrets_box


@contextmanager
def _direct_session(engine: Engine) -> Iterator[Session]:
    """A session outside the app's request lifecycle (always closed)."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_deployment_tables(engine: Engine) -> Iterator[None]:
    """The deployment-level tables these tests write to are not user-owned,
    so the ``client`` fixture's cascade truncate never reaches them; keep
    them clean between tests (the app import may have bootstrapped a key)."""
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE provider_credentials, server_settings"))


def _seed_credential(session: Session, box: SecretsBox, secret: str) -> None:
    """A stored strava credential set with the given (plaintext) secret."""
    ProviderCredentialDao(session).add(
        ProviderCredential(
            provider="strava",
            client_id="12345",
            client_secret=box.encrypt(secret),
            display_name="Homelab Strava",
        )
    )
    session.commit()


class TestSecretsBoxBootstrap:
    def test_first_call_generates_and_stores_a_valid_key(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            session.execute(text("TRUNCATE server_settings"))  # simulate a fresh deployment
            session.commit()
            assert ServerSettingDao(session).get_by_key(SECRET_KEY_SETTING) is None
            box = ensure_secrets_box(session)

        with _direct_session(engine) as session:
            row = ServerSettingDao(session).get_by_key(SECRET_KEY_SETTING)
            assert row is not None
            Fernet(row.value.encode())  # must be a valid Fernet key
            assert box.decrypt(box.encrypt("hello")) == "hello"

    def test_second_call_reuses_the_stored_key(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            first = ensure_secrets_box(session)
            ciphertext = first.encrypt("hello")
            second = ensure_secrets_box(session)

            count = session.execute(select(func.count()).select_from(ServerSetting)).scalar_one()
            assert count == 1  # still exactly one key row, however many calls
        assert second.decrypt(ciphertext) == "hello"  # same key, so it decrypts


class TestBuildProviderRegistry:
    def test_no_credentials_no_adapters(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            session.execute(text("TRUNCATE provider_credentials"))
            session.commit()
            box = ensure_secrets_box(session)
            registry = build_provider_registry(get_settings(), session, box)
        try:
            assert registry.available() == []
        finally:
            registry.close_all()

    def test_stored_credentials_register_the_adapter(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            box = ensure_secrets_box(session)
            _seed_credential(session, box, "s3cret")
            registry = build_provider_registry(get_settings(), session, box)
        try:
            assert registry.available() == ["strava"]
            # Built from the decrypted credentials: the client id is live
            # in the adapter's authorize URL.
            url = registry.get("strava").authorize_url("state-token")
            assert "client_id=12345" in url
        finally:
            registry.close_all()

    def test_soft_deleted_credentials_are_not_registered(self, engine: Engine) -> None:
        with _direct_session(engine) as session:
            box = ensure_secrets_box(session)
            _seed_credential(session, box, "s3cret")
            ProviderCredentialDao(session).mark_deleted("strava")
            session.commit()
            registry = build_provider_registry(get_settings(), session, box)
        try:
            assert registry.available() == []
        finally:
            registry.close_all()

    def test_undecryptable_secret_is_skipped_with_an_error_log(
        self, engine: Engine, caplog: pytest.LogCaptureFixture
    ) -> None:
        with _direct_session(engine) as session:
            box = ensure_secrets_box(session)
            # A row whose secret is not a token from this key (e.g. the
            # table was restored alongside a different key).
            ProviderCredentialDao(session).add(
                ProviderCredential(provider="strava", client_id="12345", client_secret="junk")
            )
            session.commit()
            with caplog.at_level(logging.ERROR, logger="app.providers.factory"):
                registry = build_provider_registry(get_settings(), session, box)
        try:
            assert registry.available() == []
        finally:
            registry.close_all()
        assert "cannot be decrypted" in caplog.text

    def test_close_all_is_a_noop_for_an_empty_registry(self) -> None:
        ProviderRegistry().close_all()
