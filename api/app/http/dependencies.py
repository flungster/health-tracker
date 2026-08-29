"""FastAPI dependencies: service construction and current-user resolution.

Building services per request keeps them explicitly wired to the
request-scoped unit of work (and, for the import service, to the settings),
and keeps route handlers free of construction code.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dao.activity_dao import ActivityDao
from app.dao.activity_hr_zone_dao import ActivityHrZoneDao
from app.dao.activity_split_dao import ActivitySplitDao
from app.dao.activity_trackpoint_dao import ActivityTrackpointDao
from app.dao.activity_type_dao import ActivityTypeDao
from app.dao.provider_account_dao import ProviderAccountDao
from app.dao.provider_credentials_dao import ProviderCredentialDao
from app.dao.provider_dao import ProviderDao
from app.dao.sport_activity_dao import (
    CyclingActivityDao,
    RowingActivityDao,
    RunningActivityDao,
    StrengthActivityDao,
)
from app.dao.user_dao import UserDao
from app.dao.user_profile_dao import UserProfileDao
from app.db.session import get_unit_of_work
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import AuthenticationError
from app.imports import build_default_detector
from app.models.user import User
from app.providers.factory import build_provider_registry
from app.providers.registry import ProviderRegistry
from app.security.passwords import PasswordService
from app.security.secrets import SecretsBox
from app.security.tokens import TokenService
from app.services.activity_service import ActivityService
from app.services.activity_stats import ActivityStatistics
from app.services.auth_service import AuthService
from app.services.import_service import ImportService
from app.services.provider_config_service import ProviderConfigService
from app.services.provider_service import ProviderService
from app.services.provider_sync_service import ProviderSyncService
from app.services.sport_service import SportService
from app.services.user_service import UserService


def get_password_service() -> PasswordService:
    """Stateless argon2 password service."""
    return PasswordService()


def get_token_service(settings: Settings = Depends(get_settings)) -> TokenService:
    """JWT service configured from the injected settings."""
    return TokenService(secret=settings.jwt_secret, ttl_days=settings.jwt_token_ttl_days)


def get_auth_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    password_service: PasswordService = Depends(get_password_service),
) -> AuthService:
    """AuthService bound to the request unit of work."""
    session: Session = unit_of_work.session
    return AuthService(unit_of_work, user_dao=UserDao(session), password_service=password_service)


def get_activity_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
) -> ActivityService:
    """ActivityService bound to the request unit of work."""
    session: Session = unit_of_work.session
    return ActivityService(
        unit_of_work,
        activity_dao=ActivityDao(session),
        trackpoint_dao=ActivityTrackpointDao(session),
        split_dao=ActivitySplitDao(session),
        hr_zone_dao=ActivityHrZoneDao(session),
        running_dao=RunningActivityDao(session),
        cycling_dao=CyclingActivityDao(session),
        rowing_dao=RowingActivityDao(session),
        strength_dao=StrengthActivityDao(session),
    )


def get_import_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    settings: Settings = Depends(get_settings),
) -> ImportService:
    """ImportService bound to the request unit of work and the settings."""
    session: Session = unit_of_work.session
    return ImportService(
        unit_of_work,
        activity_dao=ActivityDao(session),
        trackpoint_dao=ActivityTrackpointDao(session),
        split_dao=ActivitySplitDao(session),
        hr_zone_dao=ActivityHrZoneDao(session),
        running_dao=RunningActivityDao(session),
        cycling_dao=CyclingActivityDao(session),
        rowing_dao=RowingActivityDao(session),
        strength_dao=StrengthActivityDao(session),
        profile_dao=UserProfileDao(session),
        detector=build_default_detector(),
        statistics=ActivityStatistics(),
        settings=settings,
    )


def get_sport_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
) -> SportService:
    """SportService reading the global sport type reference table."""
    return SportService(activity_type_dao=ActivityTypeDao(unit_of_work.session))


def get_user_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    password_service: PasswordService = Depends(get_password_service),
) -> UserService:
    """UserService bound to the request unit of work."""
    session: Session = unit_of_work.session
    return UserService(
        unit_of_work,
        user_dao=UserDao(session),
        profile_dao=UserProfileDao(session),
        password_service=password_service,
    )


def get_provider_registry(request: Request) -> ProviderRegistry:
    """The process-wide provider registry, built at app startup."""
    # ``app.state`` is Starlette's untyped attribute bag (Any), so bind it
    # to the concrete type here.
    registry: ProviderRegistry = request.app.state.provider_registry
    return registry


def get_provider_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    registry: ProviderRegistry = Depends(get_provider_registry),
    token_service: TokenService = Depends(get_token_service),
) -> ProviderService:
    """ProviderService bound to the request unit of work and the registry."""
    session: Session = unit_of_work.session
    return ProviderService(
        unit_of_work,
        account_dao=ProviderAccountDao(session),
        provider_dao=ProviderDao(session),
        registry=registry,
        token_service=token_service,
    )


def get_provider_sync_service(
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    registry: ProviderRegistry = Depends(get_provider_registry),
    import_service: ImportService = Depends(get_import_service),
) -> ProviderSyncService:
    """ProviderSyncService bound to the request unit of work and the registry."""
    session: Session = unit_of_work.session
    return ProviderSyncService(
        unit_of_work,
        account_dao=ProviderAccountDao(session),
        activity_dao=ActivityDao(session),
        registry=registry,
        import_service=import_service,
    )


def get_provider_config_service(
    request: Request,
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    settings: Settings = Depends(get_settings),
) -> ProviderConfigService:
    """ProviderConfigService bound to the request unit of work and the
    deployment's secrets box.

    A committed write rebuilds the process-wide provider registry (closing
    the displaced adapters' pools), so credential changes are live without a
    restart.
    """
    session: Session = unit_of_work.session
    secrets_box: SecretsBox = request.app.state.secrets_box

    def swap_registry() -> None:
        old_registry: ProviderRegistry = request.app.state.provider_registry
        new_registry = build_provider_registry(settings, session, secrets_box)
        old_registry.close_all()
        request.app.state.provider_registry = new_registry

    return ProviderConfigService(
        unit_of_work,
        credential_dao=ProviderCredentialDao(session),
        provider_dao=ProviderDao(session),
        secrets_box=secrets_box,
        registry_swap=swap_registry,
    )


def get_current_user(
    request: Request,
    unit_of_work: UnitOfWork = Depends(get_unit_of_work),
    token_service: TokenService = Depends(get_token_service),
) -> User:
    """Resolve the authenticated user from the Authorization header.

    Raises AuthenticationError (401) when the header is missing, the token
    is invalid or expired, or the account no longer exists.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Missing or malformed Authorization header.")

    user_id = token_service.verify(token.strip())
    if user_id is None:
        raise AuthenticationError("Invalid or expired token.")

    user = UserDao(unit_of_work.session).get_by_uuid(user_id)
    if user is None:
        raise AuthenticationError("Account no longer exists.")
    return user
