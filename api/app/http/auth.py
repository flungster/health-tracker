"""Authentication routes: register, login and logout."""

from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.responses import Response

from app.config import Settings, get_settings
from app.http.dependencies import get_auth_service, get_token_service
from app.http.rate_limit import limit_login, limit_register
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import LoginRequest, RegisterRequest
from app.schemas.views.user_views import AuthResponseView
from app.security.cookies import clear_session_cookie, set_session_cookie
from app.security.tokens import TokenService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_with_cookie(
    response: Response, token_service: TokenService, user_uuid: UUID, settings: Settings
) -> str:
    """Issue a session token and mirror it in the HttpOnly cookie (M22a)."""
    token = token_service.issue(user_uuid)
    set_session_cookie(
        response,
        token,
        max_age_seconds=settings.jwt_token_ttl_days * 86400,
        secure=settings.session_cookie_secure,
    )
    return token


@router.post("/register", status_code=201, response_model=AuthResponseView)
def register(
    request: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    # Side-effect dependency: throttles this IP (429 when over the limit).
    _throttled: None = Depends(limit_register),
) -> AuthResponseView:
    """Create an account and return a session token (also set as a cookie)."""
    user = auth_service.register(request)
    return AuthResponseView(
        user=UserMapper.to_view(user),
        token=_issue_with_cookie(response, token_service, user.uuid, settings),
    )


@router.post("/login", response_model=AuthResponseView)
def login(
    request: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    # Side-effect dependency: throttles this IP (429 when over the limit).
    _throttled: None = Depends(limit_login),
) -> AuthResponseView:
    """Verify credentials and return a session token (also set as a cookie)."""
    user = auth_service.login(request)
    return AuthResponseView(
        user=UserMapper.to_view(user),
        token=_issue_with_cookie(response, token_service, user.uuid, settings),
    )


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    """Clear the session cookie.

    The bearer token itself is stateless and stays valid until it expires;
    this only ends the cookie session (e.g. for browser subresources).
    """
    clear_session_cookie(response)
