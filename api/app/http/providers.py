"""Provider routes: connect and disconnect third-party accounts (OAuth),
plus the server-level client configuration routes.

The OAuth callback is the one provider route without an Authorization
header: it is a plain browser redirect coming from the provider, so the user
is identified through the signed state token instead. Its outcome is
conveyed by redirecting the browser back into the app (``?connected=`` or
``?connect_error=``) — a browser flow cannot render a JSON error.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, Response

from app.config import Settings, get_settings
from app.errors.app_error import NotFoundError, ProviderUpstreamError, ValidationError
from app.http.dependencies import (
    get_current_user,
    get_provider_config_service,
    get_provider_service,
    get_provider_sync_service,
)
from app.models.user import User
from app.schemas.mappers.provider_mapper import ProviderAccountMapper
from app.schemas.requests.provider_requests import ClientConfigRequest
from app.schemas.views.provider_views import (
    ClientConfigView,
    ConnectUrlView,
    ProviderConnectionView,
    ProvidersView,
    SyncResultView,
)
from app.services.provider_config_service import ProviderConfigService
from app.services.provider_service import ProviderService
from app.services.provider_sync_service import ProviderSyncService

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("", response_model=ProvidersView)
def list_providers(
    provider_service: ProviderService = Depends(get_provider_service),
    current_user: User = Depends(get_current_user),
) -> ProvidersView:
    """The known providers and whether each is configured on this instance."""
    return ProvidersView(providers=provider_service.list_providers())


@router.get("/{provider}/connect", response_model=ConnectUrlView)
def connect(
    provider: str,
    provider_service: ProviderService = Depends(get_provider_service),
    current_user: User = Depends(get_current_user),
) -> ConnectUrlView:
    """The provider authorization URL; the UI opens it in the user's browser."""
    url = provider_service.get_connect_url(current_user.uuid, provider)
    return ConnectUrlView(url=url)


@router.get("/{provider}/oauth/callback")
def oauth_callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    provider_service: ProviderService = Depends(get_provider_service),
) -> RedirectResponse:
    """The provider's OAuth redirect target (browser, no JWT).

    Success and failure both end in a redirect back to the app's profile
    page, which reports the outcome to the user.
    """
    base = settings.public_base_url.rstrip("/")
    if error is not None:
        return RedirectResponse(f"{base}/profile?connect_error={provider}&reason=denied")
    try:
        provider_service.handle_oauth_callback(provider, code, state)
    except ValidationError:
        return RedirectResponse(f"{base}/profile?connect_error={provider}&reason=state")
    except (NotFoundError, ProviderUpstreamError):
        return RedirectResponse(f"{base}/profile?connect_error={provider}&reason=error")
    return RedirectResponse(f"{base}/profile?connected={provider}")


@router.get("/{provider}/connection", response_model=ProviderConnectionView)
def get_connection(
    provider: str,
    provider_service: ProviderService = Depends(get_provider_service),
    current_user: User = Depends(get_current_user),
) -> ProviderConnectionView:
    """The user's connection for a provider (no tokens, ever)."""
    account = provider_service.get_connection(current_user.uuid, provider)
    return ProviderAccountMapper.to_view(account)


@router.delete("/{provider}/connection", status_code=204)
def disconnect_connection(
    provider: str,
    provider_service: ProviderService = Depends(get_provider_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Disconnect a provider: revoke on the provider side, drop locally."""
    provider_service.disconnect(current_user.uuid, provider)
    return Response(status_code=204)


@router.post("/{provider}/sync", response_model=SyncResultView)
def sync_provider(
    provider: str,
    provider_sync_service: ProviderSyncService = Depends(get_provider_sync_service),
    current_user: User = Depends(get_current_user),
) -> SyncResultView:
    """Pull the user's new activities from a connected provider.

    A large history may span several runs; each run resumes from the stored
    cursor. Provider failures return the 502 ``PROVIDER_ERROR`` envelope,
    with a ``Retry-After`` header when the provider rate-limited.
    """
    return provider_sync_service.sync(current_user.uuid, provider)


# --- Server-level client configuration (not per-user) ----------------------
# Any authenticated user may manage the deployment's OAuth client for a
# provider; the client secret is stored encrypted and never exposed.


@router.get("/{provider}/client/config", response_model=ClientConfigView)
def get_client_config(
    provider: str,
    config_service: ProviderConfigService = Depends(get_provider_config_service),
    current_user: User = Depends(get_current_user),
) -> ClientConfigView:
    """The deployment's OAuth client for a provider (the secret is never
    exposed)."""
    return config_service.get_client_config(provider)


@router.put("/{provider}/client/config", response_model=ClientConfigView)
def save_client_config(
    provider: str,
    body: ClientConfigRequest,
    config_service: ProviderConfigService = Depends(get_provider_config_service),
    current_user: User = Depends(get_current_user),
) -> ClientConfigView:
    """Save (or replace) the deployment's OAuth client for a provider.

    The client secret is optional on an update (the stored one is kept) but
    required the first time. The provider registry is rebuilt after the
    commit, so the change is live without a restart.
    """
    return config_service.save_client_config(provider, body)


@router.delete("/{provider}/client/config", status_code=204)
def remove_client_config(
    provider: str,
    config_service: ProviderConfigService = Depends(get_provider_config_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Remove the deployment's OAuth client for a provider.

    User connections are left in place: they are orphaned (sync paused)
    until the credentials are saved again.
    """
    config_service.remove_client_config(provider)
    return Response(status_code=204)
