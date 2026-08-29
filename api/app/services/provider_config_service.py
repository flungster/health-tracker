"""Deployment-level provider client configuration.

The deployment's own OAuth client credentials (client id/secret) for one
provider — the app users connect *through* — are server-level state: any
authenticated user may manage them (single-family homelab assumption), the
client secret is encrypted with the deployment's ``SecretsBox`` before it
reaches the database, and no view ever exposes it. Per-user connections
(the users' own tokens) live in ``ProviderService``.

Removing a provider's client does not touch user connections: they are left
orphaned (sync paused) until credentials are saved again — re-saving the
same app resumes sync silently.
"""

import logging
from collections.abc import Callable

from app.dao.provider_credentials_dao import ProviderCredentialDao
from app.dao.provider_dao import ProviderDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.models.provider_credential import ProviderCredential
from app.schemas.mappers.provider_mapper import ProviderCredentialMapper
from app.schemas.requests.provider_requests import ClientConfigRequest
from app.schemas.views.provider_views import ClientConfigView
from app.security.secrets import SecretsBox, SecretsError

logger = logging.getLogger(__name__)

MAX_CLIENT_ID_LENGTH = 128
MAX_CLIENT_SECRET_LENGTH = 512
MAX_DISPLAY_NAME_LENGTH = 100


class ProviderConfigService:
    """Reads and writes the deployment's OAuth client for one provider."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        credential_dao: ProviderCredentialDao,
        provider_dao: ProviderDao,
        secrets_box: SecretsBox,
        registry_swap: Callable[[], None],
    ) -> None:
        self._unit_of_work = unit_of_work
        self._credential_dao = credential_dao
        self._provider_dao = provider_dao
        self._secrets_box = secrets_box
        # Rebuilds the process-wide provider registry after a committed
        # write, so credential changes are live without a restart.
        self._registry_swap = registry_swap

    def get_client_config(self, provider: str) -> ClientConfigView:
        """The deployment's client for a provider, masked.

        ``configured`` is true only for an active row whose stored secret
        decrypts; a row with an undecryptable secret reports unconfigured
        (with the client id still visible) so the UI can offer re-saving.
        """
        self._require_known_provider(provider)
        credential = self._credential_dao.get_active(provider)
        configured = credential is not None and self._secret_is_readable(credential)
        return ProviderCredentialMapper.to_view(credential, provider, configured)

    def save_client_config(self, provider: str, request: ClientConfigRequest) -> ClientConfigView:
        """Upsert the deployment's client for a provider (200, masked view).

        The secret is kept when omitted (or null); it is required the first
        time a provider is configured. ``display_name`` is kept when omitted
        and cleared when null. Reconfiguring reuses the single
        ``(provider)`` row, including a soft-deleted one.
        """
        self._require_known_provider(provider)
        client_id = request.client_id.strip()
        if not client_id:
            raise ValidationError("client_id must not be empty.")
        if len(client_id) > MAX_CLIENT_ID_LENGTH:
            raise ValidationError(f"client_id is too long (max {MAX_CLIENT_ID_LENGTH} characters).")

        secret = request.client_secret.strip() if request.client_secret is not None else None
        existing = self._credential_dao.get_any(provider)
        if secret is not None:
            if not secret:
                raise ValidationError("client_secret must not be empty.")
            if len(secret) > MAX_CLIENT_SECRET_LENGTH:
                raise ValidationError(
                    f"client_secret is too long (max {MAX_CLIENT_SECRET_LENGTH} characters)."
                )

        has_display_name = "display_name" in request.model_fields_set
        if has_display_name:
            display_name = (
                request.display_name.strip() if request.display_name is not None else None
            )
            # An empty label is the same as none.
            if display_name == "":
                display_name = None
            if display_name is not None and len(display_name) > MAX_DISPLAY_NAME_LENGTH:
                raise ValidationError(
                    f"display_name is too long (max {MAX_DISPLAY_NAME_LENGTH} characters)."
                )
        else:
            display_name = existing.display_name if existing is not None else None

        if existing is None:
            if secret is None:
                raise ValidationError("client_secret is required when no secret is stored yet.")
            credential = ProviderCredential(
                provider=provider,
                client_id=client_id,
                client_secret=self._secrets_box.encrypt(secret),
                display_name=display_name,
            )
            self._credential_dao.add(credential)
            event = "configured"
        else:
            if secret is None and existing.deleted_at is not None:
                # A soft-deleted row is "unconfigured": reconfiguring it
                # needs a secret, like a first-time configuration.
                raise ValidationError("client_secret is required when no secret is stored yet.")
            existing.client_id = client_id
            if secret is not None:
                existing.client_secret = self._secrets_box.encrypt(secret)
            if has_display_name:
                existing.display_name = display_name
            existing.deleted_at = None
            self._credential_dao.save(existing)
            credential = existing
            event = "updated"
        self._unit_of_work.commit()
        logger.info("%s client credentials for %s saved", event, provider)
        self._registry_swap()
        return ProviderCredentialMapper.to_view(credential, provider, True)

    def remove_client_config(self, provider: str) -> None:
        """Soft-delete the deployment's client for a provider (204).

        User connections are left in place (orphaned: sync paused until the
        credentials are saved again).
        """
        self._require_known_provider(provider)
        if self._credential_dao.get_active(provider) is None:
            raise NotFoundError(f"No client credentials stored for {provider}.")
        self._credential_dao.mark_deleted(provider)
        self._unit_of_work.commit()
        logger.info("Client credentials for %s removed", provider)
        self._registry_swap()

    def _require_known_provider(self, provider: str) -> None:
        """404 when the provider value is not in the reference table."""
        if self._provider_dao.get_by_value(provider) is None:
            raise NotFoundError(f"Unknown provider {provider!r}.")

    def _secret_is_readable(self, credential: ProviderCredential) -> bool:
        """Whether the stored secret decrypts with this deployment's key."""
        try:
            self._secrets_box.decrypt(credential.client_secret)
            return True
        except SecretsError:
            logger.error(
                "The stored %s client secret cannot be decrypted; the provider "
                "reads as unconfigured until the credentials are re-saved.",
                credential.provider,
            )
            return False
