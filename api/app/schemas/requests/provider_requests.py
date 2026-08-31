"""Request schemas for providers: the server-level client configuration and
the per-user connection settings."""

from datetime import date

from pydantic import BaseModel


class ConnectionPatchRequest(BaseModel):
    """Changes to a user's provider connection.

    ``sync_since`` is the import-from floor: an ISO 8601 date (``YYYY-MM-DD``)
    — activities started on or after it (UTC) are what syncs import — or
    null to remove the floor (import everything).
    """

    sync_since: date | None = None


class SyncRequest(BaseModel):
    """Optional sync run parameters.

    ``since`` (an ISO 8601 date) overrides the connection's saved
    import-from floor for this run only — a one-off rescan from a date.
    """

    since: date | None = None


class ClientConfigRequest(BaseModel):
    """The deployment's OAuth client for one provider.

    ``client_secret``: provide it to set or replace the secret; omit it (or
    send null) on an update to keep the stored one — it is required the
    first time a provider is configured. ``display_name``: omitted keeps the
    current label, null clears it.
    """

    client_id: str
    client_secret: str | None = None
    display_name: str | None = None
