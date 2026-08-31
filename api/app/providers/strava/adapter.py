"""Strava adapter: OAuth 2.0 (authorization-code flow) + v3 API.

Implements the provider-agnostic ``ProviderAdapter`` contract on top of
``StravaClient``. Strava's ``/athlete`` endpoints always operate on the
authenticated athlete, so this adapter can only ever fetch the connected
user's own activities.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx

from app.errors.app_error import ProviderUpstreamError
from app.imports.parsed import ParsedActivity
from app.imports.timeutil import parse_iso8601
from app.providers.base import (
    ActivityIdPage,
    Provider,
    ProviderAdapter,
    ProviderCredentials,
    ProviderIdentity,
)
from app.providers.strava.client import (
    DEFAULT_API_BASE_URL,
    DEFAULT_PER_PAGE,
    StravaClient,
)
from app.providers.strava.convert import strava_activity_to_parsed

DEFAULT_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"


class StravaAdapter(ProviderAdapter):
    """Adapts Strava to the app's core concepts.

    Stateless per user: credentials and sync state are passed in per call
    (they live in ``provider_accounts``).
    """

    provider: ClassVar[str] = Provider.STRAVA.value

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str,
        *,
        api_base_url: str = DEFAULT_API_BASE_URL,
        authorize_url: str = DEFAULT_AUTHORIZE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._scope = scope
        self._authorize_url = authorize_url
        self._client = StravaClient(
            client_id, client_secret, api_base_url=api_base_url, transport=transport
        )

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()

    def authorize_url(self, state: str) -> str:
        params = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": self._scope,
                "response_type": "code",
                "approval_prompt": "auto",
                "state": state,
            }
        )
        return f"{self._authorize_url}?{params}"

    def exchange_code(self, code: str) -> ProviderCredentials:
        body = self._client.post_token({"grant_type": "authorization_code", "code": code})
        return self._credentials_from_token_response(body)

    def refresh(self, credentials: ProviderCredentials) -> ProviderCredentials:
        """Fetch a fresh access token; the refresh token rotates on Strava."""
        body = self._client.post_token(
            {"grant_type": "refresh_token", "refresh_token": credentials.refresh_token}
        )
        return self._credentials_from_token_response(body)

    def fetch_identity(self, access_token: str) -> ProviderIdentity:
        body = self._client.get_athlete(access_token)
        if body.get("id") is None:
            raise ProviderUpstreamError("Strava athlete response is missing the athlete id.")
        return ProviderIdentity(
            external_user_id=str(body["id"]),
            display_name=_display_name(body),
        )

    def fetch_activity_ids(
        self, access_token: str, cursor: str | None, *, start_date: int | None = None
    ) -> ActivityIdPage:
        before = self._decode_cursor(cursor)
        summaries = self._client.list_activity_summaries(
            access_token,
            before=before,
            start_date=start_date,
            per_page=DEFAULT_PER_PAGE,
        )
        external_ids: list[str] = []
        for entry in summaries:
            if entry.get("id") is not None:
                external_ids.append(str(entry["id"]))

        # The walk goes newest -> oldest. The cursor is the unix start
        # timestamp of the page's oldest activity; the next call passes it
        # as ``before`` to fetch the older page. The boundary activity may be
        # returned twice (Strava treats ``before`` as inclusive) — harmless,
        # the dedup index on (provider, external_activity_id) imports it once.
        next_cursor: str | None = None
        if len(summaries) >= DEFAULT_PER_PAGE and summaries:
            oldest = summaries[-1]
            started = parse_iso8601(_as_str(oldest.get("start_date")))
            if started is not None:
                next_cursor = str(int(started.timestamp()))
        return ActivityIdPage(external_activity_ids=external_ids, next_cursor=next_cursor)

    def fetch_activity(self, access_token: str, external_activity_id: str) -> ParsedActivity:
        body = self._client.get_activity(access_token, external_activity_id)
        return strava_activity_to_parsed(body)

    def revoke(self, credentials: ProviderCredentials) -> None:
        self._client.post_revoke(credentials.refresh_token)

    @staticmethod
    def _decode_cursor(cursor: str | None) -> int | None:
        """The opaque cursor as the unix ``before`` timestamp, or None."""
        if cursor is None:
            return None
        try:
            before = int(cursor)
        except ValueError:
            raise ProviderUpstreamError(
                "The stored Strava sync cursor is invalid; disconnect and reconnect to reset it."
            ) from None
        return before if before > 0 else None

    @staticmethod
    def _credentials_from_token_response(body: dict[str, Any]) -> ProviderCredentials:
        """Map a /oauth/token response to credentials (dynamic JSON, narrowed here)."""
        for field_name in ("access_token", "refresh_token", "scope"):
            value = body.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ProviderUpstreamError(
                    f"Strava token response is missing {field_name!r}; "
                    "the connection may have been revoked."
                )
        expires_at = _parse_unix(body.get("expires_at"))
        athlete = body.get("athlete")
        athlete = athlete if isinstance(athlete, dict) else {}
        return ProviderCredentials(
            access_token=body["access_token"].strip(),
            refresh_token=body["refresh_token"].strip(),
            token_expires_at=expires_at,
            scope=body["scope"].strip(),
            external_user_id=str(athlete["id"]) if athlete.get("id") is not None else None,
            display_name=_display_name(athlete),
        )


def _display_name(athlete: dict[str, Any]) -> str | None:
    """'First Last' from an athlete summary, or None when not provided."""
    parts: list[str] = []
    for key in ("firstname", "lastname"):
        value = athlete.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts) or None


def _parse_unix(value: Any) -> datetime:
    """A unix timestamp (Strava's ``expires_at``) as a UTC datetime."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderUpstreamError("Strava token response is missing expires_at.")
    return datetime.fromtimestamp(value, tz=UTC)


def _as_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
