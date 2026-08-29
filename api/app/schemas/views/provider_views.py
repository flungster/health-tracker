"""View schemas for providers and provider connections.

Views are the only representation of models that leaves the API. In
particular, no view ever carries OAuth tokens.
"""

from datetime import datetime

from pydantic import BaseModel


class ProviderInfoView(BaseModel):
    """A known provider and whether it is usable on this instance."""

    value: str
    description: str
    configured: bool


class ProvidersView(BaseModel):
    """All known providers (reference data) with their configured flag."""

    providers: list[ProviderInfoView]


class ConnectUrlView(BaseModel):
    """The provider authorization URL to open in the user's browser."""

    url: str


class ProviderConnectionView(BaseModel):
    """One of the user's connected provider accounts.

    Public identity and sync state only — refresh/access tokens never leave
    the API.
    """

    provider: str
    external_user_id: str
    display_name: str | None
    connected_at: datetime
    last_sync_at: datetime | None


class SyncResultView(BaseModel):
    """The outcome of one sync run.

    ``skipped`` counts activities already imported (deduped); a large
    history may span several runs (the stored cursor resumes where the
    previous one stopped), so counts are per run, not per connection.
    """

    imported: int
    skipped: int
    last_sync_at: datetime


class ClientConfigView(BaseModel):
    """The deployment's OAuth client for a provider, masked.

    The client secret never leaves the API; ``configured`` is true only
    when a stored credential set exists and its secret decrypts.
    """

    provider: str
    configured: bool
    client_id: str | None
    display_name: str | None
