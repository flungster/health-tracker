"""Mapping between provider credentials, the ORM model, and API views."""

from uuid import UUID

from app.models.provider_account import ProviderAccount
from app.providers.base import ProviderCredentials
from app.schemas.views.provider_views import ProviderConnectionView


class ProviderAccountMapper:
    """Translates provider data between the three representation layers."""

    @staticmethod
    def from_credentials(
        user_uuid: UUID,
        provider: str,
        credentials: ProviderCredentials,
        external_user_id: str,
    ) -> ProviderAccount:
        """A new connection row from an OAuth code exchange.

        ``external_user_id`` is resolved by the service (from the token
        response or a follow-up identity fetch) so the NOT NULL column always
        gets a value.
        """
        return ProviderAccount(
            user_id=user_uuid,
            provider=provider,
            external_user_id=external_user_id,
            display_name=credentials.display_name,
            refresh_token=credentials.refresh_token,
            access_token=credentials.access_token,
            token_expires_at=credentials.token_expires_at,
            scope=credentials.scope,
        )

    @staticmethod
    def apply_credentials(
        account: ProviderAccount, credentials: ProviderCredentials, external_user_id: str
    ) -> None:
        """Replace the OAuth credentials on an existing row (reconnection).

        Also reactivates a soft-deleted row: ``UNIQUE (user_id, provider)``
        allows exactly one row per (user, provider), so reconnecting reuses it
        instead of inserting. Sync state starts fresh: the next sync walks the
        history from the top again (already-imported activities are deduped).
        """
        account.external_user_id = external_user_id
        account.display_name = credentials.display_name
        account.refresh_token = credentials.refresh_token
        account.access_token = credentials.access_token
        account.token_expires_at = credentials.token_expires_at
        account.scope = credentials.scope
        account.sync_cursor = None
        account.last_sync_at = None
        account.deleted_at = None

    @staticmethod
    def to_view(account: ProviderAccount) -> ProviderConnectionView:
        """Map a connection row to its public view (tokens excluded)."""
        return ProviderConnectionView(
            provider=account.provider,
            external_user_id=account.external_user_id,
            display_name=account.display_name,
            connected_at=account.created_at,
            last_sync_at=account.last_sync_at,
        )
