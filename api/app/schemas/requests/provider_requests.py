"""Request schemas for provider client configuration (server-level)."""

from pydantic import BaseModel


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
