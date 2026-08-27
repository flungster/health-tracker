"""Tests for StravaClient: request construction and failure mapping.

Uses httpx.MockTransport, so no network is involved; the recorded requests
are asserted on directly.
"""

import base64

import httpx
import pytest

from app.errors.app_error import ProviderUpstreamError
from app.providers.strava.client import StravaClient

API_BASE = "https://strava.test/api/v3"


def _client(handler: "object") -> StravaClient:
    return StravaClient(
        "test-client-id",
        "test-secret",
        api_base_url=API_BASE,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


class TestRequestConstruction:
    def test_post_token_sends_app_credentials_and_grant(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json={"access_token": "at"})

        body = _client(handler).post_token({"grant_type": "authorization_code", "code": "abc123"})

        request = seen["request"]
        assert request.method == "POST"
        assert request.url.path == "/api/v3/oauth/token"
        form = request.content.decode()
        assert "grant_type=authorization_code" in form
        assert "code=abc123" in form
        assert "client_id=test-client-id" in form
        assert "client_secret=test-secret" in form
        # Secrets never appear in the URL.
        assert "test-secret" not in str(request.url)
        assert body == {"access_token": "at"}

    def test_get_athlete_sends_bearer_token(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json={"id": 12345})

        body = _client(handler).get_athlete("secret-token")

        request = seen["request"]
        assert request.url.path == "/api/v3/athlete"
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert body == {"id": 12345}

    def test_list_activity_summaries_omits_before_on_first_page(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json=[])

        _client(handler).list_activity_summaries("secret-token", before=None)

        request = seen["request"]
        assert request.url.path == "/api/v3/athlete/activities"
        query = request.url.params
        assert "before" not in query
        assert query["per_page"] == "100"

    def test_list_activity_summaries_passes_before_cursor(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json=[])

        _client(handler).list_activity_summaries("secret-token", before=1751362800)

        assert seen["request"].url.params["before"] == "1751362800"

    def test_get_activity_targets_the_external_id(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(200, json={"id": 42})

        _client(handler).get_activity("secret-token", "42")

        assert seen["request"].url.path == "/api/v3/activities/42"

    def test_revoke_sends_basic_auth_and_token(self) -> None:
        seen: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["request"] = request
            return httpx.Response(204)

        _client(handler).post_revoke("the-refresh-token")

        request = seen["request"]
        expected = base64.b64encode(b"test-client-id:test-secret").decode()
        assert request.url.path == "/api/v3/oauth/revoke"
        assert request.headers["Authorization"] == f"Basic {expected}"
        assert "token=the-refresh-token" in request.content.decode()


class TestErrorMapping:
    def test_401_raises_reauthorization_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": True, "message": "Bad Authorization"})

        with pytest.raises(ProviderUpstreamError, match="re-authorized"):
            _client(handler).get_athlete("stale-token")

    def test_429_carries_retry_after(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "30"})

        with pytest.raises(ProviderUpstreamError) as excinfo:
            _client(handler).get_athlete("secret-token")
        assert excinfo.value.retry_after_seconds == 30
        assert "rate limit" in excinfo.value.message

    def test_429_without_retry_after(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        with pytest.raises(ProviderUpstreamError) as excinfo:
            _client(handler).get_athlete("secret-token")
        assert excinfo.value.retry_after_seconds is None

    def test_provider_error_uses_detail_field(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = {
                "error": True,
                "message": "Bad Request",
                "detail": "The activity does not exist.",
            }
            return httpx.Response(400, json=body)

        with pytest.raises(ProviderUpstreamError, match="The activity does not exist."):
            _client(handler).get_activity("secret-token", "999")

    def test_5xx_without_body(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="maintenance")

        with pytest.raises(ProviderUpstreamError, match="HTTP 503"):
            _client(handler).get_athlete("secret-token")

    def test_transport_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(ProviderUpstreamError, match="Could not reach Strava"):
            _client(handler).get_athlete("secret-token")

    def test_non_json_success_body(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json")

        with pytest.raises(ProviderUpstreamError, match="non-JSON"):
            _client(handler).get_athlete("secret-token")
