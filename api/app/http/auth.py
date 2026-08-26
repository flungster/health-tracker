"""Authentication routes: register and login."""

from fastapi import APIRouter, Depends

from app.http.dependencies import get_auth_service, get_token_service
from app.http.rate_limit import limit_login, limit_register
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import LoginRequest, RegisterRequest
from app.schemas.views.user_views import AuthResponseView
from app.security.tokens import TokenService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=AuthResponseView)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
    # Side-effect dependency: throttles this IP (429 when over the limit).
    _throttled: None = Depends(limit_register),
) -> AuthResponseView:
    """Create an account and return a session token."""
    user = auth_service.register(request)
    return AuthResponseView(
        user=UserMapper.to_view(user),
        token=token_service.issue(user.id),
    )


@router.post("/login", response_model=AuthResponseView)
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    token_service: TokenService = Depends(get_token_service),
    # Side-effect dependency: throttles this IP (429 when over the limit).
    _throttled: None = Depends(limit_login),
) -> AuthResponseView:
    """Verify credentials and return a session token."""
    user = auth_service.login(request)
    return AuthResponseView(
        user=UserMapper.to_view(user),
        token=token_service.issue(user.id),
    )
