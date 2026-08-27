"""Tests for the Strava adapter (request flow, cursor semantics, identity)
and the Strava JSON → ParsedActivity conversion (fixture-driven).
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.errors.app_error import ProviderUpstreamError
from app.imports.parsed import ParsedActivity
from app.providers.base import ProviderCredentials
from app.providers.strava import StravaAdapter
from app.providers.strava.convert import strava_activity_to_parsed

API_BASE = "https://strava.test/api/v3"
AUTHORIZE_URL = "https://strava.test/oauth/authorize"
FIXTURES = Path(__file__).parent / "fixtures" / "strava"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _adapter(handler: "object") -> StravaAdapter:
    return StravaAdapter(
        "cid",
        "csecret",
        redirect_uri="http://localhost:9090/api/v1/providers/strava/callback",
        scope="activity:read_all",
        api_base_url=API_BASE,
        authorize_url=AUTHORIZE_URL,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def _token_response(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "access_token": "at-123",
        "refresh_token": "rt-123",
        "expires_at": 1800000000,
        "token_type": "Bearer",
        "scope": "activity:read_all",
        "athlete": {"id": 12345, "firstname": "Alice", "lastname": "Doe"},
    }
    body.update(overrides)
    return body


class TestAuthorizeUrl:
    def test_carries_oauth_parameters(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("authorize_url must not perform any HTTP call")

        url = _adapter(handler).authorize_url("state-xyz")

        parts = urlsplit(url)
        assert f"{parts.scheme}://{parts.netloc}{parts.path}" == AUTHORIZE_URL
        params = parse_qs(parts.query)
        assert params["client_id"] == ["cid"]
        assert params["redirect_uri"] == ["http://localhost:9090/api/v1/providers/strava/callback"]
        assert params["scope"] == ["activity:read_all"]
        assert params["response_type"] == ["code"]
        assert params["approval_prompt"] == ["auto"]
        assert params["state"] == ["state-xyz"]


class TestCredentials:
    def test_exchange_code_maps_credentials(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json=_token_response())

        credentials = _adapter(handler).exchange_code("the-code")

        form = seen["request"].content.decode()
        assert "grant_type=authorization_code" in form
        assert "code=the-code" in form
        assert credentials.access_token == "at-123"
        assert credentials.refresh_token == "rt-123"
        assert credentials.scope == "activity:read_all"
        assert credentials.token_expires_at == datetime.fromtimestamp(1800000000, tz=UTC)
        assert credentials.external_user_id == "12345"
        assert credentials.display_name == "Alice Doe"

    def test_refresh_rotates_the_refresh_token(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json=_token_response(refresh_token="rt-456"))

        old = ProviderCredentials(
            refresh_token="rt-123",
            access_token="at-stale",
            token_expires_at=datetime.now(UTC),
            scope="activity:read_all",
        )
        credentials = _adapter(handler).refresh(old)

        form = seen["request"].content.decode()
        assert "grant_type=refresh_token" in form
        assert "refresh_token=rt-123" in form
        # Strava invalidates the old refresh token; the latest is returned.
        assert credentials.refresh_token == "rt-456"

    def test_token_response_without_scope_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = _token_response()
            del body["scope"]
            return httpx.Response(200, json=body)

        with pytest.raises(ProviderUpstreamError, match="scope"):
            _adapter(handler).exchange_code("the-code")


class TestIdentityAndRevoke:
    def test_fetch_identity_maps_athlete(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": 12345, "firstname": "Alice", "lastname": "Doe"})

        identity = _adapter(handler).fetch_identity("at-123")

        assert identity.external_user_id == "12345"
        assert identity.display_name == "Alice Doe"

    def test_fetch_identity_requires_an_id(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"firstname": "NoId"})

        with pytest.raises(ProviderUpstreamError):
            _adapter(handler).fetch_identity("at-123")

    def test_revoke_sends_the_stored_refresh_token(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(204)

        credentials = ProviderCredentials(
            refresh_token="rt-123",
            access_token="at-123",
            token_expires_at=datetime.now(UTC),
            scope="activity:read_all",
        )
        _adapter(handler).revoke(credentials)

        assert seen["request"].url.path == "/api/v3/oauth/revoke"
        assert "token=rt-123" in seen["request"].content.decode()


class TestActivityIdPages:
    def _summaries(
        self, count: int, start_date: str = "2026-07-15T10:00:00Z"
    ) -> list[dict[str, Any]]:
        return [
            {"id": 10000 - index, "name": f"Activity {index}", "start_date": start_date}
            for index in range(count)
        ]

    def test_short_page_ends_the_walk(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=self._summaries(2))

        page = _adapter(handler).fetch_activity_ids("at-123", None)

        assert page.external_activity_ids == ["10000", "9999"]
        assert page.next_cursor is None

    def test_full_page_advances_the_cursor(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=self._summaries(100))

        page = _adapter(handler).fetch_activity_ids("at-123", None)

        expected = str(int(datetime(2026, 7, 15, 10, 0, tzinfo=UTC).timestamp()))
        assert len(page.external_activity_ids) == 100
        assert page.next_cursor == expected

    def test_cursor_is_sent_as_before(self) -> None:
        # The walk goes newest -> oldest, so the cursor is sent as ``before``
        # (fetch the older page), not ``after`` (which would loop the same page).
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json=self._summaries(1))

        _adapter(handler).fetch_activity_ids("at-123", "1751362800")

        assert seen["request"].url.params["before"] == "1751362800"

    def test_garbage_cursor_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("a bad cursor must fail before any HTTP call")

        with pytest.raises(ProviderUpstreamError, match="cursor"):
            _adapter(handler).fetch_activity_ids("at-123", "not-a-timestamp")

    def test_empty_page_ends_the_walk(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        page = _adapter(handler).fetch_activity_ids("at-123", None)

        assert page.external_activity_ids == []
        assert page.next_cursor is None


class TestConversion:
    def test_running_activity(self) -> None:
        parsed = strava_activity_to_parsed(_load("activity_running.json"))

        assert isinstance(parsed, ParsedActivity)
        assert parsed.sport_type == "running"
        assert parsed.name == "Morning Run"
        assert parsed.description == "Easy effort before work"
        assert parsed.started_at == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
        assert parsed.ended_at == datetime(2026, 8, 1, 9, 48, 20, tzinfo=UTC)
        assert parsed.duration_seconds == 2900
        assert parsed.moving_seconds == 2760
        assert parsed.distance_m == 8213.4
        assert parsed.calories_kcal == 512.4
        assert parsed.elevation_gain_m == 62.1
        # Summary values (fallbacks when trackpoints lack samples).
        assert parsed.heart_rate_avg_bpm == 152
        assert parsed.heart_rate_max_bpm == 171
        assert parsed.cadence_avg_rpm == 85
        assert parsed.sport_metrics.power_avg_w is None
        assert parsed.warnings == []

        assert len(parsed.trackpoints) == 5
        first = parsed.trackpoints[0]
        assert first.recorded_at == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
        assert first.lat == 52.3702
        assert first.lon == 4.8952
        assert first.altitude_m == 2.1
        assert first.heart_rate_bpm == 121
        assert first.cadence_rpm == 78
        assert first.speed_mps == 2.4
        assert first.power_w is None
        # Trackpoint times are offsets from the start, not absolute times.
        last = parsed.trackpoints[-1]
        assert last.recorded_at == datetime(2026, 8, 1, 9, 48, 20, tzinfo=UTC)

    def test_rowing_activity_without_trackpoints(self) -> None:
        parsed = strava_activity_to_parsed(_load("activity_rowing.json"))

        assert parsed.sport_type == "rowing"
        assert parsed.name == "Erg Session"
        assert parsed.description is None
        assert parsed.started_at == datetime(2026, 8, 2, 18, 30, tzinfo=UTC)
        assert parsed.ended_at == datetime(2026, 8, 2, 19, 5, 0, tzinfo=UTC)
        assert parsed.duration_seconds == 2100
        assert parsed.moving_seconds == 1800
        assert parsed.distance_m == 6000.0
        assert parsed.calories_kcal == 410.0
        # 0 is not a meaningful elevation; stays None.
        assert parsed.elevation_gain_m is None
        assert parsed.heart_rate_avg_bpm == 143
        assert parsed.heart_rate_max_bpm == 165
        assert parsed.cadence_avg_rpm == 26
        assert parsed.trackpoints == []
        assert parsed.warnings == []

    def test_strength_activity_reports_no_distance(self) -> None:
        parsed = strava_activity_to_parsed(_load("activity_strength.json"))

        assert parsed.sport_type == "strength"
        assert parsed.name == "Leg Day"
        assert parsed.distance_m is None
        assert parsed.calories_kcal is None
        assert parsed.elevation_gain_m is None
        assert parsed.heart_rate_avg_bpm is None
        assert parsed.heart_rate_max_bpm is None
        assert parsed.cadence_avg_rpm is None
        assert parsed.duration_seconds == 5400
        assert parsed.moving_seconds == 4200
        assert parsed.trackpoints == []
        assert parsed.warnings == []

    def test_unknown_sport_maps_to_other_with_warning(self) -> None:
        data = {"sport_type": "AlpineSki", "start_date": "2026-08-01T09:00:00Z"}
        parsed = strava_activity_to_parsed(data)

        assert parsed.sport_type == "other"
        assert any("AlpineSki" in warning for warning in parsed.warnings)

    def test_missing_sport_stays_none(self) -> None:
        parsed = strava_activity_to_parsed({"start_date": "2026-08-01T09:00:00Z"})

        assert parsed.sport_type is None
        assert parsed.warnings == []

    def test_heartrate_opt_out_hides_hr_and_warns(self) -> None:
        data = {
            "sport_type": "Running",
            "start_date": "2026-08-01T09:00:00Z",
            "average_heartrate": 150.0,
            "max_heartrate": 170.0,
            "heartrate_opt_out": True,
        }
        parsed = strava_activity_to_parsed(data)

        assert parsed.heart_rate_avg_bpm is None
        assert parsed.heart_rate_max_bpm is None
        assert any("hidden heart rate" in warning for warning in parsed.warnings)

    def test_minimal_activity_imports(self) -> None:
        data = {"sport_type": "Running", "start_date": "2026-08-01T09:00:00Z"}
        parsed = strava_activity_to_parsed(data)

        assert parsed.started_at == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
        assert parsed.ended_at is None
        assert parsed.duration_seconds is None
        assert parsed.distance_m is None
        assert parsed.trackpoints == []

    def test_malformed_trackpoints_are_tolerated(self) -> None:
        data = {
            "sport_type": "Running",
            "start_date": "2026-08-01T09:00:00Z",
            "elapsed_time": 60,
            "track_points": [
                "garbage",
                {"time": "not-a-number"},
                {
                    "time": 30,
                    "latitude": None,
                    "longitude": 5.0,
                    "altitude": 1.5,
                    "heart_rate": 0,
                    "cadence": -5,
                    "speed": -1,
                },
            ],
        }
        parsed = strava_activity_to_parsed(data)

        # Non-dict entries are dropped; the rest are kept null-safe.
        assert len(parsed.trackpoints) == 2
        assert parsed.trackpoints[0].recorded_at is None
        second = parsed.trackpoints[1]
        assert second.recorded_at == datetime(2026, 8, 1, 9, 0, 30, tzinfo=UTC)
        assert second.lat is None
        assert second.lon == 5.0
        assert second.heart_rate_bpm is None
        assert second.cadence_rpm is None
        assert second.speed_mps is None
