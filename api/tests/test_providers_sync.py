"""Tests for the provider sync (M10d, M11e): the paged walk, dedup, cursor
checkpoints/resume, token refresh, rate-limit handling, the import-from
floor, and the API route.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.dao.provider_account_dao import ProviderAccountDao
from app.main import app
from app.models.activity import Activity
from app.models.provider_account import ProviderAccount
from app.providers import ProviderRegistry
from app.providers.strava import StravaAdapter

API_BASE = "https://strava.test/api/v3"
API_PATH = "/api/v3"  # the path part of API_BASE (requests carry no host)
AUTHORIZE_URL = "https://strava.test/oauth/authorize"
FUTURE_TOKEN_EXPIRY = datetime(2030, 1, 1, tzinfo=UTC)

# The ``register_user`` fixture (a factory) is defined in tests/conftest.py.
# It is typed Any here to keep this file independent of the fixture module.


PAGE_SIZE = 100  # must match the adapter's per-page request


def _activities(count: int, start_unix: int, id_base: int) -> list[dict[str, Any]]:
    """``count`` activities, all starting at the same unix timestamp."""
    return [
        {"id": id_base - index, "name": f"Activity {id_base - index}", "start_unix": start_unix}
        for index in range(count)
    ]


def _iso(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=UTC).isoformat().replace("+00:00", "Z")


def _detail_body(external_id: int) -> dict[str, Any]:
    return {
        "id": external_id,
        "sport_type": "Running",
        "name": "Synced Run",
        "start_date": "2026-08-01T09:00:00Z",
        "distance": 10000.0,
        "elapsed_time": 3000,
        "moving_time": 2900,
    }


class MockStrava:
    """A stateful mock Strava: paged activity list, per-id detail, tokens.

    The list endpoint honors the ``before`` cursor and the ``start_date``
    floor like the real API: it returns the newest activities started before
    the cursor and at or after the floor (100 per page), so re-walks,
    resumes, and floored walks behave as they would against Strava.
    ``second_list_call_limited`` makes the second list call answer 429 with a
    Retry-After, to exercise the stop-and-resume path.
    """

    def __init__(
        self, activities: list[dict[str, Any]], second_list_call_limited: bool = False
    ) -> None:
        # Newest first, like the real endpoint.
        self._activities = sorted(activities, key=lambda a: a["start_unix"], reverse=True)
        self._second_list_call_limited = second_list_call_limited
        self.list_calls = 0
        self.list_params: list[dict[str, str]] = []
        self.detail_ids: list[int] = []
        self.token_grants: list[str] = []
        self.auth_seen: list[str] = []

    def _page(self, before_unix: int | None, start_unix: int | None) -> list[dict[str, Any]]:
        rows = self._activities
        if start_unix is not None:
            rows = [a for a in rows if a["start_unix"] >= start_unix]
        if before_unix is not None:
            rows = [a for a in rows if a["start_unix"] < before_unix]
        return rows[:PAGE_SIZE]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/oauth/token"):
            form = request.content.decode()
            self.token_grants.append("refresh" if "grant_type=refresh_token" in form else "code")
            return httpx.Response(
                200,
                json={
                    "access_token": "at-2",
                    "refresh_token": "rt-2",
                    "expires_at": int(FUTURE_TOKEN_EXPIRY.timestamp()),
                    "token_type": "Bearer",
                    "scope": "activity:read_all",
                    "athlete": {"id": 12345, "firstname": "Alice", "lastname": "Doe"},
                },
            )
        if path.endswith("/athlete/activities"):
            self.list_calls += 1
            self.auth_seen.append(request.headers.get("Authorization", ""))
            if self._second_list_call_limited and self.list_calls == 2:
                return httpx.Response(
                    429, json={"detail": "Rate limit exceeded."}, headers={"Retry-After": "30"}
                )
            self.list_params.append(dict(request.url.params))
            before = request.url.params.get("before")
            before_unix = int(before) if before is not None else None
            start = request.url.params.get("start_date")
            start_unix = int(start) if start is not None else None
            page = self._page(before_unix, start_unix)
            summaries = [
                {"id": a["id"], "name": a["name"], "start_date": _iso(a["start_unix"])}
                for a in page
            ]
            return httpx.Response(200, json=summaries)
        if path.startswith(f"{API_PATH}/activities/"):
            external_id = int(path.rsplit("/", 1)[1])
            self.detail_ids.append(external_id)
            self.auth_seen.append(request.headers.get("Authorization", ""))
            return httpx.Response(200, json=_detail_body(external_id))
        return httpx.Response(404, json={"detail": "unexpected endpoint"})


def _registry_with(mock: MockStrava) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        StravaAdapter(
            "cid",
            "csecret",
            redirect_uri="http://localhost:9090/api/v1/providers/strava/oauth/callback",
            scope="activity:read_all",
            api_base_url=API_BASE,
            authorize_url=AUTHORIZE_URL,
            transport=httpx.MockTransport(mock.handler),
        )
    )
    return registry


class SyncFixture:
    """A connected-user sync environment: mock registry, seeded connection,
    and readers over the test database."""

    def __init__(
        self,
        client: TestClient,
        engine: Engine,
        mock: MockStrava,
        token: str,
        user_uuid: UUID,
    ) -> None:
        self.client = client
        self.engine = engine
        self.mock = mock
        self.token = token
        self.user_uuid = user_uuid

    def seed_connection(
        self,
        *,
        token_expires_at: datetime = FUTURE_TOKEN_EXPIRY,
        access_token: str = "at-1",
        refresh_token: str = "rt-1",
        sync_cursor: str | None = None,
        sync_since: datetime | None = None,
    ) -> None:
        """Insert an active provider account row outside the request lifecycle."""
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = factory()
        try:
            session.add(
                ProviderAccount(
                    user_id=self.user_uuid,
                    provider="strava",
                    external_user_id="12345",
                    display_name="Alice Doe",
                    refresh_token=refresh_token,
                    access_token=access_token,
                    token_expires_at=token_expires_at,
                    scope="activity:read_all",
                    sync_cursor=sync_cursor,
                    sync_since=sync_since,
                )
            )
            session.commit()
        finally:
            session.close()

    def read_account(self) -> dict[str, Any] | None:
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = factory()
        try:
            account = ProviderAccountDao(session).get_for_user(self.user_uuid, "strava")
            if account is None:
                return None
            return {
                "sync_cursor": account.sync_cursor,
                "last_sync_at": account.last_sync_at,
                "access_token": account.access_token,
                "refresh_token": account.refresh_token,
                "sync_since": account.sync_since,
            }
        finally:
            session.close()

    def read_provenance(self) -> dict[str, Any] | None:
        """Provenance of one strava-imported activity (any)."""
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = factory()
        try:
            row = session.execute(
                select(
                    Activity.provider, Activity.external_activity_id, Activity.source_format
                ).where(Activity.provider == "strava")
            ).first()
            if row is None:
                return None
            return {"provider": row[0], "external_activity_id": row[1], "source_format": row[2]}
        finally:
            session.close()


@pytest.fixture
def sync_env(
    client: TestClient,
    engine: Engine,
    register_user: Any,
    request: pytest.FixtureRequest,
) -> Iterator[SyncFixture]:
    """A registered user plus a mock-transport registry on the app.

    Parametrize with the mock: ``pytest.param(MockStrava(pages), id=...)``
    and ``indirect=True`` on the ``sync_env`` parameter.
    """
    mock: MockStrava = request.param
    body: dict[str, Any] = register_user()
    token: str = body["token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    user_uuid = UUID(me.json()["id"])

    original = app.state.provider_registry
    app.state.provider_registry = _registry_with(mock)
    try:
        yield SyncFixture(client, engine, mock, token, user_uuid)
    finally:
        app.state.provider_registry = original


def _full_history() -> list[dict[str, Any]]:
    """102 activities across two start timestamps (two list pages)."""
    return [
        *_activities(100, int(datetime(2026, 8, 1, 9, 0, tzinfo=UTC).timestamp()), id_base=9000),
        *_activities(2, int(datetime(2026, 7, 1, 9, 0, tzinfo=UTC).timestamp()), id_base=8000),
    ]


def _small_history() -> list[dict[str, Any]]:
    return _activities(2, int(datetime(2026, 8, 1, 9, 0, tzinfo=UTC).timestamp()), id_base=500)


def _sync_response(env: SyncFixture, since: str | None = None) -> httpx.Response:
    json_body: dict[str, Any] | None = None
    if since is not None:
        json_body = {"since": since}
    response: httpx.Response = env.client.post(
        "/api/v1/providers/strava/sync",
        headers={"Authorization": f"Bearer {env.token}"},
        json=json_body,
    )
    return response


class TestSyncWalk:
    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_full_history()), id="two-pages")], indirect=True
    )
    def test_first_sync_imports_full_history(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection()

        response = _sync_response(sync_env)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        assert body["imported"] == 102
        assert body["skipped"] == 0
        assert body["last_sync_at"] is not None

        feed = sync_env.client.get(
            "/api/v1/activities?limit=1", headers={"Authorization": f"Bearer {sync_env.token}"}
        ).json()
        assert feed["total"] == 102

        # The walk finished: cursor cleared, last_sync_at stamped.
        account = sync_env.read_account()
        assert account is not None
        assert account["sync_cursor"] is None
        assert account["last_sync_at"] is not None

        # Provider provenance: no file format, external id recorded.
        provenance = sync_env.read_provenance()
        assert provenance is not None
        assert provenance["provider"] == "strava"
        assert provenance["source_format"] is None
        assert provenance["external_activity_id"] is not None

        assert len(sync_env.mock.detail_ids) == 102
        assert len(set(sync_env.mock.detail_ids)) == 102

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_full_history()), id="two-pages")], indirect=True
    )
    def test_resync_skips_imported(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection()

        first = _sync_response(sync_env)
        assert first.status_code == 200
        assert first.json()["imported"] == 102

        second = _sync_response(sync_env)
        assert second.status_code == 200
        second_body: dict[str, Any] = second.json()
        assert second_body["imported"] == 0
        assert second_body["skipped"] == 102

        feed = sync_env.client.get(
            "/api/v1/activities?limit=1", headers={"Authorization": f"Bearer {sync_env.token}"}
        ).json()
        assert feed["total"] == 102

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_full_history()), id="two-pages")], indirect=True
    )
    def test_partial_run_resumes_from_cursor(
        self, sync_env: SyncFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.services.provider_sync_service.MAX_SYNC_PAGES", 1)
        sync_env.seed_connection()

        first = _sync_response(sync_env)
        assert first.status_code == 200
        first_body: dict[str, Any] = first.json()
        assert first_body["imported"] == 100
        assert first_body["skipped"] == 0
        account = sync_env.read_account()
        assert account is not None
        assert account["sync_cursor"] is not None  # paused mid-walk
        assert account["last_sync_at"] is not None  # the run completed (partially)

        # The next run resumes from the cursor: only the tail page is fetched.
        second = _sync_response(sync_env)
        assert second.status_code == 200
        second_body: dict[str, Any] = second.json()
        assert second_body["imported"] == 2
        assert second_body["skipped"] == 0
        account = sync_env.read_account()
        assert account is not None
        assert account["sync_cursor"] is None  # walk finished

        feed = sync_env.client.get(
            "/api/v1/activities?limit=1", headers={"Authorization": f"Bearer {sync_env.token}"}
        ).json()
        assert feed["total"] == 102


class TestSyncTokens:
    @pytest.mark.parametrize(
        "sync_env",
        [pytest.param(MockStrava(_small_history()), id="ok")],
        indirect=True,
    )
    def test_expired_token_is_refreshed_and_rotated(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection(
            token_expires_at=datetime.now(UTC) - timedelta(hours=1),
            access_token="at-old",
            refresh_token="rt-old",
        )

        response = _sync_response(sync_env)
        assert response.status_code == 200, response.text

        assert sync_env.mock.token_grants == ["refresh"]
        # All activity calls used the fresh token, not the expired one.
        assert set(sync_env.mock.auth_seen) == {"Bearer at-2"}
        # The rotated pair is persisted (the old refresh token is dead).
        account = sync_env.read_account()
        assert account is not None
        assert account["refresh_token"] == "rt-2"
        assert account["access_token"] == "at-2"

    @pytest.mark.parametrize(
        "sync_env",
        [pytest.param(MockStrava(_small_history()), id="ok")],
        indirect=True,
    )
    def test_fresh_token_is_not_refreshed(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection(access_token="at-fresh")

        response = _sync_response(sync_env)
        assert response.status_code == 200

        assert sync_env.mock.token_grants == []
        assert set(sync_env.mock.auth_seen) == {"Bearer at-fresh"}


class TestSyncFailures:
    @pytest.mark.parametrize(
        "sync_env",
        [pytest.param(MockStrava(_full_history(), second_list_call_limited=True), id="limited")],
        indirect=True,
    )
    def test_rate_limit_stops_walk_and_keeps_cursor(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection()

        response = _sync_response(sync_env)
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "PROVIDER_ERROR"
        assert response.headers["Retry-After"] == "30"

        # Page 1 landed; the cursor points at the resume point; last_sync_at
        # is untouched because the run did not complete.
        feed = sync_env.client.get(
            "/api/v1/activities?limit=1", headers={"Authorization": f"Bearer {sync_env.token}"}
        ).json()
        assert feed["total"] == 100
        account = sync_env.read_account()
        assert account is not None
        assert account["sync_cursor"] is not None
        assert account["last_sync_at"] is None

    def test_sync_without_connection_404s(
        self,
        client: TestClient,
        register_user: Any,
    ) -> None:
        token: str = register_user()["token"]
        response = client.post(
            "/api/v1/providers/strava/sync", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_sync_unconfigured_provider_404s(
        self, client: TestClient, register_user: Any, engine: Engine
    ) -> None:
        # No mock registry: the app's real registry has no Strava configured.
        body: dict[str, Any] = register_user()
        token: str = body["token"]
        me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        user_uuid = UUID(me.json()["id"])

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        try:
            session.add(
                ProviderAccount(
                    user_id=user_uuid,
                    provider="strava",
                    external_user_id="12345",
                    refresh_token="rt-1",
                    access_token="at-1",
                    token_expires_at=FUTURE_TOKEN_EXPIRY,
                    scope="activity:read_all",
                )
            )
            session.commit()
        finally:
            session.close()

        response = client.post(
            "/api/v1/providers/strava/sync", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404

    def test_sync_requires_authentication(self, client: TestClient) -> None:
        assert client.post("/api/v1/providers/strava/sync").status_code == 401


OLD_UNIX = int(datetime(2026, 1, 15, 10, 0, tzinfo=UTC).timestamp())
NEW_UNIX = int(datetime(2026, 8, 1, 9, 0, tzinfo=UTC).timestamp())


def _mixed_history() -> list[dict[str, Any]]:
    """One old activity (January) and one new one (August)."""
    return [
        {"id": 101, "name": "Old Run", "start_unix": OLD_UNIX},
        {"id": 102, "name": "New Run", "start_unix": NEW_UNIX},
    ]


class TestSyncLookback:
    """The walk's import-from floor: the request's ``since`` overrides the
    connection's saved ``sync_since``, and the floor bounds every page."""

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_mixed_history()), id="mixed")], indirect=True
    )
    def test_since_imports_only_activities_at_or_after_it(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection()

        response = _sync_response(sync_env, since="2026-06-01")
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        assert body["imported"] == 1
        assert body["skipped"] == 0

        provenance = sync_env.read_provenance()
        assert provenance is not None
        assert provenance["external_activity_id"] == "102"

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_mixed_history()), id="mixed")], indirect=True
    )
    def test_saved_floor_bounds_the_walk_without_a_request(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection(sync_since=datetime(2026, 6, 1, tzinfo=UTC))

        response = _sync_response(sync_env)
        assert response.status_code == 200, response.text
        assert response.json()["imported"] == 1

        provenance = sync_env.read_provenance()
        assert provenance is not None
        assert provenance["external_activity_id"] == "102"

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_mixed_history()), id="mixed")], indirect=True
    )
    def test_request_since_overrides_the_saved_floor(self, sync_env: SyncFixture) -> None:
        # A wide saved floor (all of 2026) plus a narrow one-off rescan.
        sync_env.seed_connection(sync_since=datetime(2026, 1, 1, tzinfo=UTC))

        response = _sync_response(sync_env, since="2026-06-01")
        assert response.status_code == 200, response.text
        assert response.json()["imported"] == 1

        provenance = sync_env.read_provenance()
        assert provenance is not None
        assert provenance["external_activity_id"] == "102"

        # The override is one-off: the saved floor is untouched.
        account = sync_env.read_account()
        assert account is not None
        assert account["sync_since"] == datetime(2026, 1, 1, tzinfo=UTC)

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_mixed_history()), id="mixed")], indirect=True
    )
    def test_the_floor_applies_to_every_page(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection(sync_since=datetime(2026, 6, 1, tzinfo=UTC))

        response = _sync_response(sync_env)
        assert response.status_code == 200

        # The floor (UTC midnight of 2026-06-01) was sent on every list call.
        expected = str(int(datetime(2026, 6, 1, tzinfo=UTC).timestamp()))
        assert sync_env.mock.list_calls >= 1
        assert all(call.get("start_date") == expected for call in sync_env.mock.list_params)

    @pytest.mark.parametrize(
        "sync_env",
        [
            pytest.param(
                MockStrava(
                    [
                        *_activities(100, NEW_UNIX, id_base=9000),
                        *_activities(
                            2, int(datetime(2026, 7, 1, 9, 0, tzinfo=UTC).timestamp()), id_base=8000
                        ),
                    ]
                ),
                id="two-pages-floored",
            )
        ],
        indirect=True,
    )
    def test_a_floored_walk_stops_at_the_floor(
        self, sync_env: SyncFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 100 activities in August (a full page) plus 2 in July, with the
        # floor between them: the walk must page past the first page, fetch
        # the (empty) tail, and finish — importing only the August page.
        monkeypatch.setattr("app.services.provider_sync_service.MAX_SYNC_PAGES", 2)
        sync_env.seed_connection(sync_since=datetime(2026, 7, 15, tzinfo=UTC))

        response = _sync_response(sync_env)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        assert body["imported"] == 100
        assert body["skipped"] == 0

        account = sync_env.read_account()
        assert account is not None
        assert account["sync_cursor"] is None  # the walk completed at the floor
        assert sync_env.mock.list_calls == 2

    @pytest.mark.parametrize(
        "sync_env", [pytest.param(MockStrava(_mixed_history()), id="mixed")], indirect=True
    )
    def test_malformed_since_422s(self, sync_env: SyncFixture) -> None:
        sync_env.seed_connection()

        response: httpx.Response = sync_env.client.post(
            "/api/v1/providers/strava/sync",
            headers={"Authorization": f"Bearer {sync_env.token}"},
            json={"since": "not-a-date"},
        )
        assert response.status_code == 422
