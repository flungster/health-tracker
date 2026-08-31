"""Provider contracts: the provider-agnostic half of the third-party
integration layer.

A ``ProviderAdapter`` turns one external provider (Strava, later Garmin,
Polar, ...) into the app's core concepts: OAuth credentials, the connected
user's own identity, and their activities as ``ParsedActivity`` objects.
The core (provider accounts, sync loop, import) is provider-agnostic and
talks to adapters through this contract only.

Adapters only ever fetch data for the connected user's OWN account; there
is no support for fetching other people's activities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from app.imports.parsed import ParsedActivity


class Provider(StrEnum):
    """Code-side mirror of the ``providers`` reference table.

    Values must match the seeded rows (the schema-level source of truth,
    enforced by the ``provider_accounts``/``activities`` foreign keys).
    """

    STRAVA = "strava"


@dataclass
class ProviderCredentials:
    """OAuth credentials for one connection (the token fields of a
    ``provider_accounts`` row).

    ``external_user_id``/``display_name`` are optional extras some providers
    return with the token exchange (Strava returns an athlete summary).
    """

    refresh_token: str
    access_token: str
    token_expires_at: datetime
    scope: str
    external_user_id: str | None = None
    display_name: str | None = None


@dataclass
class ProviderIdentity:
    """The connected user's own profile on the provider."""

    external_user_id: str
    display_name: str | None = None


@dataclass
class ActivityIdPage:
    """One page of the user's activity ids on the provider.

    ``next_cursor`` is ``None`` when there are no more pages. The cursor is
    opaque to the core: it is persisted as-is on the provider account and
    handed back unchanged on the next call.
    """

    external_activity_ids: list[str] = field(default_factory=list)
    next_cursor: str | None = None


class ProviderAdapter(ABC):
    """One external provider, adapted to the app's core.

    Adapters are stateless with respect to per-user data: user-specific
    state (tokens, sync cursor) lives in ``provider_accounts`` and is passed
    in per call. Network failures raise ``ProviderUpstreamError``; input
    problems raise the usual ``AppError`` subclasses.
    """

    #: Value in the ``providers`` reference table (matches ``Provider``).
    provider: ClassVar[str]

    @abstractmethod
    def authorize_url(self, state: str) -> str:
        """The provider authorization URL to send the user's browser to.

        ``state`` is the app-signed CSRF/state token; the provider returns
        it verbatim to the callback.
        """

    @abstractmethod
    def exchange_code(self, code: str) -> ProviderCredentials:
        """Exchange an authorization code for credentials (one-time use)."""

    @abstractmethod
    def refresh(self, credentials: ProviderCredentials) -> ProviderCredentials:
        """Fetch a fresh access token (the refresh token may rotate)."""

    @abstractmethod
    def fetch_identity(self, access_token: str) -> ProviderIdentity:
        """The connected user's own profile on the provider."""

    @abstractmethod
    def fetch_activity_ids(
        self, access_token: str, cursor: str | None, *, start_date: int | None = None
    ) -> ActivityIdPage:
        """The next page of the user's activity ids, newest first.

        ``cursor`` is the opaque resume point from the previous page
        (``None`` for the first page). ``start_date`` is an optional unix
        lower bound: only activities started at or after it are returned
        (the walk's floor; it applies to every page of the walk).
        """

    @abstractmethod
    def fetch_activity(self, access_token: str, external_activity_id: str) -> ParsedActivity:
        """Full detail for one of the user's activities, as a ParsedActivity."""

    @abstractmethod
    def revoke(self, credentials: ProviderCredentials) -> None:
        """Revoke the connection on the provider (best effort)."""

    def close(self) -> None:  # noqa: B027 — an intentional default no-op
        """Release the resources the adapter holds (e.g. an HTTP pool).

        The default is a no-op for adapters that hold none; adapters with
        connection pools override it. Called when the registry holding the
        adapter is replaced.
        """
