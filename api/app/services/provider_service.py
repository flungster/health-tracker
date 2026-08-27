"""Provider connection business logic: the OAuth flow and account rows.

The user's browser performs the OAuth redirect dance (connect button ->
provider -> callback). The callback carries no Authorization header, so the
user is identified through the signed ``state`` token issued at connect time
— which also stops forged or crossed flows (CSRF).
"""

import logging
from uuid import UUID

from app.dao.provider_account_dao import ProviderAccountDao
from app.dao.provider_dao import ProviderDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ProviderUpstreamError, ValidationError
from app.models.provider_account import ProviderAccount
from app.providers.base import ProviderAdapter, ProviderCredentials
from app.providers.registry import ProviderRegistry
from app.schemas.mappers.provider_mapper import ProviderAccountMapper
from app.schemas.views.provider_views import ProviderInfoView
from app.security.tokens import TokenService

logger = logging.getLogger(__name__)


class ProviderService:
    """Manages a user's provider connections (one row per user + provider)."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        account_dao: ProviderAccountDao,
        provider_dao: ProviderDao,
        registry: ProviderRegistry,
        token_service: TokenService,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._account_dao = account_dao
        self._provider_dao = provider_dao
        self._registry = registry
        self._token_service = token_service

    def list_providers(self) -> list[ProviderInfoView]:
        """Every known provider, with a flag for whether it is configured."""
        configured = set(self._registry.available())
        views: list[ProviderInfoView] = []
        for provider in self._provider_dao.list_all():
            views.append(
                ProviderInfoView(
                    value=provider.value,
                    description=provider.description,
                    configured=provider.value in configured,
                )
            )
        return views

    def get_connect_url(self, user_uuid: UUID, provider: str) -> str:
        """The provider authorization URL to open in the user's browser.

        Raises NotFoundError when the provider is unknown or not configured
        on this instance.
        """
        adapter = self._registry.get(provider)
        state = self._token_service.issue_oauth_state(user_uuid)
        url = adapter.authorize_url(state)
        logger.info("Issued OAuth connect URL for user %s -> %s", user_uuid, provider)
        return url

    def handle_oauth_callback(
        self, provider: str, code: str | None, state: str | None
    ) -> ProviderAccount:
        """Complete the OAuth code exchange and store the connection.

        The user is the one bound to the ``state`` token. Raises
        ValidationError when the state is missing, invalid, or expired (the
        flow must be restarted from the connect button) and NotFoundError
        when the provider is not configured.
        """
        if code is None or state is None:
            raise ValidationError("The provider callback is missing its code or state.")
        user_uuid = self._token_service.verify_oauth_state(state)
        if user_uuid is None:
            raise ValidationError("Invalid or expired OAuth state; please try again.")
        adapter = self._registry.get(provider)
        credentials = adapter.exchange_code(code)
        external_user_id = self._resolve_external_user_id(adapter, credentials)

        account = self._account_dao.get_any_for_user(user_uuid, provider)
        if account is None:
            account = ProviderAccountMapper.from_credentials(
                user_uuid, provider, credentials, external_user_id
            )
            self._account_dao.add(account)
            event = "connected"
        else:
            ProviderAccountMapper.apply_credentials(account, credentials, external_user_id)
            self._account_dao.save(account)
            event = "reconnected"
        self._unit_of_work.commit()
        logger.info("User %s %s %s (external id %s)", user_uuid, event, provider, external_user_id)
        return account

    def get_connection(self, user_uuid: UUID, provider: str) -> ProviderAccount:
        """The user's active connection for a provider.

        Raises NotFoundError when there is none (including when the provider
        is unknown or not configured).
        """
        account = self._account_dao.get_for_user(user_uuid, provider)
        if account is None:
            raise NotFoundError(f"No {provider} connection for this account.")
        return account

    def disconnect(self, user_uuid: UUID, provider: str) -> None:
        """Drop the user's connection: revoke on the provider, soft-delete.

        Revocation is best effort — the provider may have expired the tokens
        already; the local connection is dropped either way.
        """
        account = self._account_dao.get_for_user(user_uuid, provider)
        if account is None:
            raise NotFoundError(f"No {provider} connection to disconnect.")
        adapter = self._registry.get(provider)
        credentials = ProviderCredentials(
            refresh_token=account.refresh_token,
            access_token=account.access_token,
            token_expires_at=account.token_expires_at,
            scope=account.scope,
        )
        try:
            adapter.revoke(credentials)
        except ProviderUpstreamError as exc:
            logger.warning(
                "Could not revoke %s connection for user %s: %s",
                provider,
                user_uuid,
                exc.message,
            )
        self._account_dao.mark_deleted(user_uuid, provider)
        self._unit_of_work.commit()
        logger.info("User %s disconnected %s", user_uuid, provider)

    @staticmethod
    def _resolve_external_user_id(
        adapter: ProviderAdapter, credentials: ProviderCredentials
    ) -> str:
        """The connected user's external id: from the token response, or a
        follow-up identity fetch for providers that do not return it."""
        if credentials.external_user_id is not None:
            return credentials.external_user_id
        return adapter.fetch_identity(credentials.access_token).external_user_id
