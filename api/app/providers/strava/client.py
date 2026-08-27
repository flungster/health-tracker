"""Thin synchronous HTTP client for the Strava v3 API.

Transport only: builds requests, sends them, decodes JSON, and maps
failures onto ``ProviderUpstreamError``. Domain interpretation (credentials,
identity, activities) lives in ``adapter.py``/``convert.py``.

Access tokens are sent in request headers or form fields only; they are
never part of any URL and never included in log messages or exceptions.
"""

from typing import Any

import httpx

from app.errors.app_error import ProviderUpstreamError

DEFAULT_API_BASE_URL = "https://www.strava.com/api/v3"
DEFAULT_PER_PAGE = 100
_TIMEOUT_SECONDS = 30.0


class StravaClient:
    """Minimal client for the Strava v3 endpoints the app uses.

    Every method either returns decoded JSON or raises
    ``ProviderUpstreamError`` (network failure, rate limit, or provider
    error). The client holds no per-user state.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        api_base_url: str = DEFAULT_API_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_base_url = api_base_url.rstrip("/")
        self._http = httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            transport=transport,
            headers={"User-Agent": "health-tracker"},
        )

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._http.close()

    def post_token(self, form: dict[str, str]) -> dict[str, Any]:
        """POST /oauth/token (authorization-code exchange or refresh).

        ``form`` carries the grant-specific fields (``grant_type`` +
        ``code`` or ``refresh_token``); the app credentials are added here.
        """
        merged = {"client_id": self._client_id, "client_secret": self._client_secret, **form}
        body = self._request("POST", "/oauth/token", form=merged)
        if not isinstance(body, dict):
            raise ProviderUpstreamError("Unexpected Strava token response.")
        return body

    def post_revoke(self, token: str) -> None:
        """POST /oauth/revoke — disconnect on the Strava side (best effort)."""
        form = {"client_id": self._client_id, "client_secret": self._client_secret, "token": token}
        # Strava requires Basic auth in addition to the form fields here.
        auth = httpx.BasicAuth(self._client_id, self._client_secret)
        response = self._http.post(self._url("/oauth/revoke"), data=form, auth=auth)
        self._raise_for_status(response)

    def get_athlete(self, access_token: str) -> dict[str, Any]:
        """GET /athlete — the authenticated (i.e. the connected user's own) athlete."""
        body = self._request("GET", "/athlete", access_token=access_token)
        if not isinstance(body, dict):
            raise ProviderUpstreamError("Unexpected Strava athlete response.")
        return body

    def list_activity_summaries(
        self,
        access_token: str,
        *,
        before: int | None,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """GET /athlete/activities — the user's activities, newest first.

        ``before`` walks the history backwards: only activities started
        before the unix timestamp are returned (the opaque sync cursor,
        decoded by the adapter). ``None`` for the first page (the most
        recent activities).
        """
        params: dict[str, str] = {"per_page": str(per_page)}
        if before is not None:
            params["before"] = str(before)
        body = self._request("GET", "/athlete/activities", access_token=access_token, params=params)
        if not isinstance(body, list):
            raise ProviderUpstreamError("Unexpected Strava activity-list response.")
        return [entry for entry in body if isinstance(entry, dict)]

    def get_activity(self, access_token: str, external_activity_id: str) -> dict[str, Any]:
        """GET /activities/{id} — full detail for one of the user's activities."""
        body = self._request(
            "GET", f"/activities/{external_activity_id}", access_token=access_token
        )
        if not isinstance(body, dict):
            raise ProviderUpstreamError("Unexpected Strava activity response.")
        return body

    def _url(self, path: str) -> str:
        return f"{self._api_base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        params: dict[str, str] | None = None,
        form: dict[str, str] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        try:
            response = self._http.request(
                method, self._url(path), params=params, data=form, headers=headers
            )
        except httpx.TransportError as exc:
            # exc messages carry hosts/times only — never credentials.
            raise ProviderUpstreamError(f"Could not reach Strava: {exc}.") from exc
        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUpstreamError(
                f"Strava returned a non-JSON response (HTTP {response.status_code})."
            ) from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 401:
            raise ProviderUpstreamError(
                "Strava rejected the credentials; the connection may need to be re-authorized."
            )
        if response.status_code == 429:
            raise ProviderUpstreamError(
                "Strava rate limit exceeded.",
                retry_after_seconds=self._retry_after_seconds(response),
            )
        raise ProviderUpstreamError(
            f"Strava error {response.status_code}: {self._provider_message(response)}"
        )

    def _provider_message(self, response: httpx.Response) -> str:
        """The human-readable part of Strava's error body, when present."""
        try:
            body = response.json()
        except ValueError:
            return f"HTTP {response.status_code}"
        if isinstance(body, dict):
            for key in ("detail", "message"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return f"HTTP {response.status_code}"

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(1, int(value))
        except ValueError:
            return None
