"""Test configuration.

Tests run against a dedicated Postgres database (``health_tracker_test``)
on the compose stack, so a running ``make up`` (at least the db service) is
required. The fixtures:

1. create the test database when missing (idempotent),
2. apply all dbmate migrations to it,
3. point the FastAPI app at it via a ``get_unit_of_work`` override,
4. truncate all rows after every test.
"""

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.session import get_unit_of_work
from app.db.unit_of_work import UnitOfWork
from app.main import app
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


@pytest.fixture(scope="session")
def test_database() -> None:
    """Ensure the test database exists and is migrated (once per session)."""
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
    return


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


@pytest.fixture
def engine(test_database: None) -> Iterator[Engine]:
    """A SQLAlchemy engine bound to the test database."""
    created = create_engine(TEST_DATABASE_URL)
    yield created
    created.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
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
            connection.execute(text("TRUNCATE user_profiles, users CASCADE"))


@pytest.fixture
def uploads_dir(tmp_path: Path) -> Iterator[Path]:
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
