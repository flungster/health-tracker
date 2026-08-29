"""Test configuration.

Tests run against a dedicated Postgres database (``health_tracker_test``)
on the compose stack, so a running ``make up`` (at least the db service) is
required. The bootstrap (``pytest_configure`` — which runs before any test
module, and thus before ``app.main``, is imported) :

1. points the app at the test database (``DATABASE_URL``),
2. creates the test database when missing (idempotent),
3. applies all dbmate migrations to it.

``create_app()`` runs at import time and reads the stored provider
credentials + bootstraps the secrets box from the configured database, so
the test database must exist, be migrated, and be the configured one before
``from app.main import app`` runs anywhere. The fixtures then point the
app's request sessions at the test database via a ``get_unit_of_work``
override and truncate all rows after every test.
"""

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.session import get_unit_of_work
from app.db.unit_of_work import UnitOfWork
from app.providers.factory import build_provider_registry
from app.providers.registry import ProviderRegistry
from app.security.rate_limiter import RateLimiter

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_PG_CREDENTIALS = "healthtracker:healthtracker"
TEST_DB_NAME = "health_tracker_test"
# Used by the test process on the host (compose forwards 127.0.0.1:5432).
TEST_DATABASE_URL = f"postgresql+psycopg://{_PG_CREDENTIALS}@localhost:5432/{TEST_DB_NAME}"
# Used by the dbmate container, which reaches Postgres as host "db" on the
# compose network. TLS is off on the compose Postgres, hence sslmode=disable.
_DBMATE_TEST_URL = f"postgresql://{_PG_CREDENTIALS}@db:5432/{TEST_DB_NAME}?sslmode=disable"


def _compose(args: list[str]) -> None:
    """Run a docker compose command from the project root."""
    subprocess.run(
        ["docker", "compose", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _ensure_test_database() -> None:
    """Create the test database (when missing) and apply all migrations."""
    # 1. Create the database when missing.
    check = _compose_capture(
        [
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "healthtracker",
            "-d",
            "health_tracker",
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname = 'health_tracker_test'",
        ]
    )
    if check.strip() != "1":
        _compose(
            [
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "healthtracker",
                "-d",
                "health_tracker",
                "-c",
                f"CREATE DATABASE {TEST_DB_NAME}",
            ]
        )
    # 2. Apply all migrations to the test database.
    _compose(["run", "--rm", "-e", f"DATABASE_URL={_DBMATE_TEST_URL}", "migrate"])


def _reset_provider_registry(app: FastAPI, engine: Engine) -> None:
    """Rebuild the process-wide provider registry from the test database.

    A client-config write in a test swaps the process-wide registry, but
    that is not a database row: the ``client`` fixture truncates the
    deployment tables after every test, and this reset rebuilds the
    registry from them so the next test starts consistent with the
    (now empty) tables.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        fresh = build_provider_registry(get_settings(), session, app.state.secrets_box)
    old_registry: ProviderRegistry = app.state.provider_registry
    old_registry.close_all()
    app.state.provider_registry = fresh


def pytest_configure(config: pytest.Config) -> None:
    """Bootstrap the test database before ``app.main`` is imported.

    ``create_app()`` (which runs at import time) bootstraps the secrets box
    and the provider registry from the configured database, so the test
    database must exist, be migrated, and be the one the app points at —
    environment variables take precedence over any ``.env`` file.
    """
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    _ensure_test_database()


def _compose_capture(args: list[str]) -> str:
    """Run a docker compose command and return its stdout."""
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """The FastAPI application under test.

    Imported here (not at module level) so that ``create_app()`` runs after
    ``pytest_configure`` has pointed the app at the migrated test database.
    """
    from app.main import app

    return app


@pytest.fixture
def engine() -> Iterator[Engine]:
    """A SQLAlchemy engine bound to the test database."""
    created = create_engine(TEST_DATABASE_URL)
    yield created
    created.dispose()


@pytest.fixture
def client(engine: Engine, app: FastAPI) -> Iterator[TestClient]:
    """A TestClient whose DB session points at the test database.

    Truncates all tables after the test finishes.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # The rate limiter is process-wide; give every test a clean slate.
    limiter: RateLimiter = app.state.rate_limiter
    limiter.reset()

    def override_get_unit_of_work() -> Iterator[UnitOfWork]:
        session: Session = factory()
        unit_of_work = UnitOfWork(session)
        try:
            yield unit_of_work
        finally:
            session.close()

    app.dependency_overrides[get_unit_of_work] = override_get_unit_of_work
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_unit_of_work, None)
        with engine.begin() as connection:
            # user-owned tables cascade from users; the deployment-level
            # tables (provider credentials, server settings) need explicit
            # truncation.
            connection.execute(
                text("TRUNCATE user_profiles, users, provider_credentials, server_settings CASCADE")
            )
        _reset_provider_registry(app, engine)


@pytest.fixture
def uploads_dir(tmp_path: Path, app: FastAPI) -> Iterator[Path]:
    """Point the import service at a temporary uploads directory.

    Done by overriding the ``get_settings`` dependency (the service receives
    its settings through injection), so no module-level monkeypatching is needed.
    """
    target = tmp_path / "uploads"
    target.mkdir()
    settings = get_settings().model_copy(update={"uploads_dir": str(target)})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield target
    finally:
        app.dependency_overrides.pop(get_settings, None)


RegisterFactory = Callable[[str, str, str, str], dict[str, object]]


@pytest.fixture
def register_user(client: TestClient) -> RegisterFactory:
    """Factory that registers a user and returns the API response body."""

    def _register(
        email: str = "alice@example.com",
        first_name: str = "Alice",
        last_name: str = "Doe",
        password: str = "supersecret1",
    ) -> dict[str, object]:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": password,
            },
        )
        assert response.status_code == 201, response.text
        body: dict[str, object] = response.json()
        return body

    return _register
