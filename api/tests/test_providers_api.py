"""Tests for the provider connection API: the OAuth flow, state binding,
connect/disconnect, and the token-never-leaves rule."""

from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import ProviderRegistry
from app.providers.strava import StravaAdapter

API_BASE = "https://strava.test/api/v3"
AUTHORIZE_URL = "https://strava.test/oauth/authorize"
CALLBACK_BASE = "http://localhost:9090/profile"

# The ``register_user`` fixture (a factory) is defined in tests/conftest.py.
# It is typed Any here to keep this file independent of the fixture module.


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


def _ok_handler(seen: list[httpx.Request] | None = None) -> "object":
    """A mock Strava: token exchange and revoke both succeed."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json=_token_response())
        if request.url.path.endswith("/oauth/revoke"):
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": "unexpected endpoint"})

    return handler


def _failing_token_handler() -> "object":
    """A mock Strava whose /oauth/token rejects the code (e.g. revoked app)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid authorization code."})

    return handler


def _make_registry(handler: "object") -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        StravaAdapter(
            "test-client-id",
            "test-client-secret",
            redirect_uri="http://localhost:9090/api/v1/providers/strava/oauth/callback",
            scope="activity:read_all",
            api_base_url=API_BASE,
            authorize_url=AUTHORIZE_URL,
            transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        )
    )
    return registry


@pytest.fixture
def provider_client(client: TestClient, request: pytest.FixtureRequest) -> Iterator[TestClient]:
    """The API client with a registry holding a mock-transport Strava adapter.

    Parametrize with the mock handler: ``pytest.param(_ok_handler(), id=...)``
    and ``indirect=True`` on the ``provider_client`` parameter.
    """
    handler = request.param
    original = app.state.provider_registry
    app.state.provider_registry = _make_registry(handler)
    try:
        yield client
    finally:
        app.state.provider_registry = original


@pytest.fixture
def recorded_strava(client: TestClient) -> Iterator[list[httpx.Request]]:
    """Registry with a mock handler that records every request; yields them."""
    seen: list[httpx.Request] = []
    original = app.state.provider_registry
    app.state.provider_registry = _make_registry(_ok_handler(seen))
    try:
        yield seen
    finally:
        app.state.provider_registry = original


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _connect_state(client: TestClient, token: str) -> str:
    """Run GET /strava/connect and return the state token from its URL."""
    response = client.get("/api/v1/providers/strava/connect", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    raw_url = response.json().get("url")
    assert isinstance(raw_url, str), "connect response carried no URL"
    assert raw_url, "connect response carried an empty URL"
    params = parse_qs(urlsplit(raw_url).query)
    return params["state"][0]


def _callback(client: TestClient, query: str) -> httpx.Response:
    """Hit the OAuth callback (a browser redirect: no auth header)."""
    # TestClient.get is typed loosely by Starlette; bind it to httpx.Response.
    response: httpx.Response = client.get(
        f"/api/v1/providers/strava/oauth/callback?{query}", follow_redirects=False
    )
    return response


def _complete_connect(client: TestClient, token: str) -> None:
    """Drive the full callback flow for a freshly issued state."""
    state = _connect_state(client, token)
    response = _callback(client, f"code=the-code&state={state}")
    assert response.status_code == 307, response.text
    assert response.headers["location"] == f"{CALLBACK_BASE}?connected=strava"


class TestListProviders:
    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_marks_strava_configured(
        self,
        provider_client: TestClient,
        register_user: Any,
    ) -> None:
        token: str = register_user()["token"]
        response = provider_client.get("/api/v1/providers", headers=_auth_headers(token))

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "providers": [{"value": "strava", "description": "Strava", "configured": True}]
        }

    def test_unconfigured_instance_reports_configured_false(
        self, client: TestClient, register_user: Any
    ) -> None:
        # The default test app has no STRAVA_CLIENT_ID/SECRET, so the registry
        # is empty: the provider is known (reference table) but not usable.
        token: str = register_user()["token"]
        response = client.get("/api/v1/providers", headers=_auth_headers(token))

        assert response.status_code == 200
        assert response.json() == {
            "providers": [{"value": "strava", "description": "Strava", "configured": False}]
        }

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/providers").status_code == 401


class TestConnect:
    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_url_carries_oauth_parameters(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        response = provider_client.get(
            "/api/v1/providers/strava/connect", headers=_auth_headers(token)
        )

        assert response.status_code == 200
        url = response.json()["url"]
        parts = urlsplit(url)
        assert f"{parts.scheme}://{parts.netloc}{parts.path}" == AUTHORIZE_URL
        params = parse_qs(parts.query)
        assert params["client_id"] == ["test-client-id"]
        assert params["redirect_uri"] == [
            "http://localhost:9090/api/v1/providers/strava/oauth/callback"
        ]
        assert params["scope"] == ["activity:read_all"]
        assert params["response_type"] == ["code"]
        assert len(params["state"]) == 1
        assert params["state"][0]

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_unknown_provider_404s(self, provider_client: TestClient, register_user: Any) -> None:
        token: str = register_user()["token"]
        response = provider_client.get(
            "/api/v1/providers/garmin/connect", headers=_auth_headers(token)
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_unconfigured_provider_404s(self, client: TestClient, register_user: Any) -> None:
        token: str = register_user()["token"]
        response = client.get("/api/v1/providers/strava/connect", headers=_auth_headers(token))

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_requires_authentication(self, provider_client: TestClient) -> None:
        assert provider_client.get("/api/v1/providers/strava/connect").status_code == 401


class TestOauthCallback:
    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_completes_the_connection(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)

        response = provider_client.get(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "strava"
        assert body["external_user_id"] == "12345"
        assert body["display_name"] == "Alice Doe"
        assert body["last_sync_at"] is None
        assert body["connected_at"]
        assert body["sync_since"] is None
        # Token material never leaves the API.
        assert set(body) == {
            "provider",
            "external_user_id",
            "display_name",
            "connected_at",
            "last_sync_at",
            "sync_since",
        }

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_rejects_invalid_state(self, provider_client: TestClient, register_user: Any) -> None:
        register_user()
        response = _callback(provider_client, "code=the-code&state=not-a-state")

        assert response.status_code == 307
        assert response.headers["location"] == f"{CALLBACK_BASE}?connect_error=strava&reason=state"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_rejects_missing_parameters(self, provider_client: TestClient) -> None:
        response = _callback(provider_client, "")

        assert response.status_code == 307
        assert response.headers["location"] == f"{CALLBACK_BASE}?connect_error=strava&reason=state"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_rejects_a_session_jwt_as_state(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        # A session JWT verifies as a valid signature but has no oauth state
        # purpose, so it must not count.
        token: str = register_user()["token"]
        response = _callback(provider_client, f"code=the-code&state={token}")

        assert response.status_code == 307
        assert response.headers["location"] == f"{CALLBACK_BASE}?connect_error=strava&reason=state"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_denial_redirects_with_reason(self, provider_client: TestClient) -> None:
        response = _callback(provider_client, "error=access_denied&state=whatever")

        assert response.status_code == 307
        assert response.headers["location"] == f"{CALLBACK_BASE}?connect_error=strava&reason=denied"

    @pytest.mark.parametrize(
        "provider_client",
        [pytest.param(_failing_token_handler(), id="failing-token")],
        indirect=True,
    )
    def test_exchange_failure_redirects_with_reason(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        state = _connect_state(provider_client, token)
        response = _callback(provider_client, f"code=the-code&state={state}")

        assert response.status_code == 307
        assert response.headers["location"] == f"{CALLBACK_BASE}?connect_error=strava&reason=error"


class TestDisconnect:
    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_revokes_and_soft_deletes(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)

        response = provider_client.delete(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )
        assert response.status_code == 204

        assert (
            provider_client.get(
                "/api/v1/providers/strava/connection", headers=_auth_headers(token)
            ).status_code
            == 404
        )

    def test_revoke_request_carries_the_refresh_token(
        self, client: TestClient, recorded_strava: list[httpx.Request], register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        _complete_connect(client, token)
        response = client.delete(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )
        assert response.status_code == 204

        revoke_requests = [r for r in recorded_strava if r.url.path.endswith("/oauth/revoke")]
        assert len(revoke_requests) == 1
        assert "token=rt-123" in revoke_requests[0].content.decode()

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_reconnect_reuses_the_row(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)
        first: dict[str, Any] = provider_client.get(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        ).json()

        assert (
            provider_client.delete(
                "/api/v1/providers/strava/connection", headers=_auth_headers(token)
            ).status_code
            == 204
        )
        _complete_connect(provider_client, token)
        second: dict[str, Any] = provider_client.get(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        ).json()

        # Same row (UNIQUE user+provider allows exactly one), so the original
        # connected_at survives the disconnect/reconnect cycle.
        assert second["connected_at"] == first["connected_at"]
        assert second["external_user_id"] == "12345"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_without_a_connection_404s(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        response = provider_client.delete(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_requires_authentication(self, provider_client: TestClient) -> None:
        assert provider_client.delete("/api/v1/providers/strava/connection").status_code == 401


class TestConnectionSettings:
    """PATCH /providers/{p}/connection: the user's import-from floor."""

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_set_the_floor_and_read_it_back(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)

        response = provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": "2026-06-01"},
        )
        assert response.status_code == 200, response.text
        # The date is stored as UTC midnight.
        assert response.json()["sync_since"].startswith("2026-06-01T00:00:00")

        get = provider_client.get(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )
        assert get.json()["sync_since"].startswith("2026-06-01T00:00:00")

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_null_clears_the_floor(self, provider_client: TestClient, register_user: Any) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)
        provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": "2026-06-01"},
        )

        response = provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": None},
        )
        assert response.status_code == 200, response.text
        assert response.json()["sync_since"] is None

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_the_floor_survives_a_reconnect(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        # A user preference, unlike the sync cursor: disconnect + reconnect
        # must not reset it.
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)
        provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": "2026-01-01"},
        )

        assert (
            provider_client.delete(
                "/api/v1/providers/strava/connection", headers=_auth_headers(token)
            ).status_code
            == 204
        )
        _complete_connect(provider_client, token)

        get = provider_client.get(
            "/api/v1/providers/strava/connection", headers=_auth_headers(token)
        )
        assert get.json()["sync_since"].startswith("2026-01-01T00:00:00")

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_without_a_connection_404s(
        self, provider_client: TestClient, register_user: Any
    ) -> None:
        token: str = register_user()["token"]
        response = provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": "2026-06-01"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_unknown_provider_404s(self, provider_client: TestClient, register_user: Any) -> None:
        token: str = register_user()["token"]
        response = provider_client.patch(
            "/api/v1/providers/garmin/connection",
            headers=_auth_headers(token),
            json={"sync_since": "2026-06-01"},
        )
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_malformed_date_422s(self, provider_client: TestClient, register_user: Any) -> None:
        token: str = register_user()["token"]
        _complete_connect(provider_client, token)
        response = provider_client.patch(
            "/api/v1/providers/strava/connection",
            headers=_auth_headers(token),
            json={"sync_since": "not-a-date"},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "provider_client", [pytest.param(_ok_handler(), id="ok")], indirect=True
    )
    def test_requires_authentication(self, provider_client: TestClient) -> None:
        response = provider_client.patch(
            "/api/v1/providers/strava/connection", json={"sync_since": "2026-06-01"}
        )
        assert response.status_code == 401
