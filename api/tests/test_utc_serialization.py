"""UTC-deterministic view serialization (M30).

The JSON contract renders a given instant as ISO 8601 UTC no matter what
timezone the process runs in. These tests pin that invariant by switching
the *process* TZ to a non-UTC zone (America/Los_Angeles) and asserting the
views still serialize in the UTC form — through pydantic's json-mode output
(the exact serialization FastAPI uses for responses) and, end to end, through
a real request with a database round-trip.

The TZ switch is a test precondition, not the fix: it must fail without the
UTC normalization in ``app.schemas.views.utc_datetime``. The existing
sync-floor assertions in tests/test_providers_api.py pin the same invariant
end to end and run under whatever TZ the host has.

Note on format: zero-offset instants render with a ``Z`` suffix — that is
what the live UTC stack already emits (see e.g. tests/test_activities.py,
which asserts ``"2024-06-01T09:00:00Z"``), so the UTC normalization must
reproduce exactly that rendering.
"""

import json
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas.views.activity_views import ActivitySummaryView, TrackpointView
from app.schemas.views.provider_views import ProviderConnectionView

_PACIFIC = ZoneInfo("America/Los_Angeles")
_PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture
def non_utc_process_tz() -> Iterator[None]:
    """Run the test under a non-UTC process TZ (America/Los_Angeles).

    ``TZ`` + ``time.tzset()`` is a process-wide switch; the previous value
    (or its absence) and the tz itself are restored afterwards so no other
    test is affected.
    """
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "America/Los_Angeles"
    time.tzset()
    try:
        yield None
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


def _json(view: object) -> dict[str, Any]:
    """The exact JSON a view serializes to (pydantic json mode = wire form)."""
    body: dict[str, Any] = json.loads(view.model_dump_json())  # type: ignore[attr-defined]
    return body


class TestUtcViewSerializationUnderNonUtcProcessTz:
    def test_local_offset_input_renders_utc(
        self,
        non_utc_process_tz: None,  # noqa: ARG002 — fixture is the precondition
    ) -> None:
        # The instant 2026-06-01T00:00Z, the way psycopg hands a timestamptz
        # back on a Pacific host (process-local offset attached).
        local = datetime(2026, 5, 31, 17, tzinfo=_PACIFIC)
        view = ProviderConnectionView(
            provider="strava",
            external_user_id="12345",
            display_name=None,
            connected_at=local,
            last_sync_at=None,
            sync_since=datetime(2026, 5, 31, 17, tzinfo=_PACIFIC),
        )

        body = _json(view)
        assert body["connected_at"] == "2026-06-01T00:00:00Z"
        assert body["sync_since"] == "2026-06-01T00:00:00Z"
        assert body["last_sync_at"] is None

    def test_utc_input_renders_identically(
        self,
        non_utc_process_tz: None,  # noqa: ARG002 — fixture is the precondition
    ) -> None:
        view = ProviderConnectionView(
            provider="strava",
            external_user_id="12345",
            display_name=None,
            connected_at=datetime(2026, 6, 1, tzinfo=UTC),
            last_sync_at=None,
            sync_since=datetime(2026, 1, 1, tzinfo=UTC),
        )

        body = _json(view)
        assert body["connected_at"] == "2026-06-01T00:00:00Z"
        assert body["sync_since"] == "2026-01-01T00:00:00Z"

    def test_positive_offset_input_renders_utc(
        self,
        non_utc_process_tz: None,  # noqa: ARG002 — fixture is the precondition
    ) -> None:
        view = ActivitySummaryView(
            id="123e4567-e89b-42d3-a456-426614174000",
            sport_type="running",
            name="Morning Run",
            started_at=datetime(2026, 6, 1, 5, 30, tzinfo=_PARIS),
            duration_seconds=1480,
            moving_seconds=None,
            distance=None,
            calories_kcal=None,
            elevation_gain=None,
            heart_rate_avg_bpm=None,
            provider=None,
        )

        body = _json(view)
        assert body["started_at"] == "2026-06-01T03:30:00Z"

    def test_optional_datetime_fields(
        self,
        non_utc_process_tz: None,  # noqa: ARG002 — fixture is the precondition
    ) -> None:
        point = TrackpointView(
            seq=1,
            recorded_at=datetime(2026, 5, 31, 17, tzinfo=_PACIFIC),
            lat=None,
            lon=None,
            altitude=None,
            heart_rate_bpm=None,
            cadence_rpm=None,
            speed=None,
            power_w=None,
        )

        body = _json(point)
        assert body["recorded_at"] == "2026-06-01T00:00:00Z"

    def test_naive_datetime_is_rejected(
        self,
        non_utc_process_tz: None,  # noqa: ARG002 — fixture is the precondition
    ) -> None:
        with pytest.raises(ValidationError):
            ProviderConnectionView(
                provider="strava",
                external_user_id="12345",
                display_name=None,
                connected_at=datetime(2026, 5, 31, 17),
                last_sync_at=None,
                sync_since=None,
            )


class TestUtcWireFormatEndToEnd:
    def test_register_response_created_at_is_utc(
        self, client: TestClient, register_user: Any, non_utc_process_tz: None
    ) -> None:
        # created_at is a database default (timestamptz), so this exercises the
        # full path: DB round-trip -> mapper -> view -> FastAPI JSON, under a
        # forced non-UTC process TZ.
        body = register_user()

        created_at: str = body["user"]["created_at"]  # type: ignore[index]
        assert created_at.endswith("Z")
        parsed = datetime.fromisoformat(created_at)
        assert parsed.utcoffset() == timedelta(0)
