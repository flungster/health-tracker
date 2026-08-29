"""Builds the process-wide provider registry from stored credentials.

The registry is rebuilt whenever the deployment's credentials change (at
startup, and after a config write from M11c on): one adapter per provider
that has an active, decryptable credential row.
"""

import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.dao.provider_credentials_dao import ProviderCredentialDao
from app.providers.base import Provider
from app.providers.registry import ProviderRegistry
from app.providers.strava import StravaAdapter
from app.security.secrets import SecretsBox, SecretsError

logger = logging.getLogger(__name__)


def build_provider_registry(
    settings: Settings, session: Session, secrets_box: SecretsBox
) -> ProviderRegistry:
    """One adapter per provider with an active credential set.

    Providers without a credential row are simply not registered (they read
    as "not available on this instance", 404). A row whose secret cannot be
    decrypted (corrupted, or restored alongside a different key) is skipped
    with an ERROR log: the provider reads as unconfigured, and re-saving the
    credentials repairs it.
    """
    registry = ProviderRegistry()
    _register_strava(settings, session, secrets_box, registry)
    return registry


def _register_strava(
    settings: Settings, session: Session, secrets_box: SecretsBox, registry: ProviderRegistry
) -> None:
    """Register the Strava adapter when the deployment has usable credentials."""
    credential = ProviderCredentialDao(session).get_active(Provider.STRAVA.value)
    if credential is None:
        return
    try:
        client_secret = secrets_box.decrypt(credential.client_secret)
    except SecretsError:
        logger.error(
            "Skipping %s: the stored client secret cannot be decrypted; "
            "re-save the provider credentials to repair it.",
            Provider.STRAVA.value,
        )
        return
    redirect_uri = settings.strava_redirect_uri or (
        f"{settings.public_base_url.rstrip('/')}/api/v1/providers/strava/oauth/callback"
    )
    registry.register(
        StravaAdapter(
            credential.client_id,
            client_secret,
            redirect_uri=redirect_uri,
            scope=settings.strava_scope,
        )
    )
