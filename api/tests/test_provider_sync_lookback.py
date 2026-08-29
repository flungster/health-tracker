"""Contract stub for sync lookback (lands in M11e): ``POST /providers/{p}/sync``
accepts an optional ``since`` (ISO 8601 date) and imports only activities
started at or after it.

Locked in now as ``xfail(strict=True)``; the marker comes off in M11e. The
mock reuses ``test_providers_sync``'s fixtures/plumbing (same directory) and
extends ``MockStrava`` to honor Strava's ``start_date`` list parameter; in
M11e the two test modules should share one mock.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from test_providers_sync import MockStrava, SyncFixture, _iso, _registry_with

from app.main import app

pytestmark = pytest.mark.xfail(
    strict=True, reason="M11e: sync lookback (since) not implemented yet"
)

OLD_UNIX = int(datetime(2026, 1, 15, 10, 0, tzinfo=UTC).timestamp())
NEW_UNIX = int(datetime(2026, 8, 1, 9, 0, tzinfo=UTC).timestamp())


class MockStravaSince(MockStrava):
    """``MockStrava`` extended to honor Strava's ``start_date`` list parameter."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/athlete/activities"):
            params = request.url.params
            rows = list(self._activities)
            start_date = params.get("start_date")
            if start_date is not None:
                start_unix = (
                    int(start_date)
                    if start_date.isdigit()
                    else int(datetime.fromisoformat(start_date.replace("Z", "+00:00")).timestamp())
                )
                rows = [a for a in rows if a["start_unix"] >= start_unix]
            before = params.get("before")
            if before is not None:
                rows = [a for a in rows if a["start_unix"] < int(before)]
            summaries = [
                {"id": a["id"], "name": a["name"], "start_date": _iso(a["start_unix"])}
                for a in rows[:100]
            ]
            return httpx.Response(200, json=summaries)
        return super().handler(request)


def _mixed_history() -> list[dict[str, Any]]:
    """One old activity (January) and one new one (August)."""
    return [
        {"id": 101, "name": "Old Run", "start_unix": OLD_UNIX},
        {"id": 102, "name": "New Run", "start_unix": NEW_UNIX},
    ]


@pytest.fixture
def lookback_env(
    client: TestClient,
    engine: Engine,
    register_user: Any,
) -> Iterator[SyncFixture]:
    """A registered user, a seeded connection, and the since-aware mock registry."""
    mock = MockStravaSince(_mixed_history())
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


class TestSyncLookback:
    def test_since_imports_only_activities_at_or_after_it(self, lookback_env: SyncFixture) -> None:
        lookback_env.seed_connection()

        response: httpx.Response = lookback_env.client.post(
            "/api/v1/providers/strava/sync",
            headers={"Authorization": f"Bearer {lookback_env.token}"},
            json={"since": "2026-06-01"},
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        assert body["imported"] == 1
        assert body["skipped"] == 0

        # Only the newer activity was imported.
        provenance = lookback_env.read_provenance()
        assert provenance is not None
        assert provenance["external_activity_id"] == "102"
