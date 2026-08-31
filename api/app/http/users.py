"""User routes: the caller's own account and profile."""

from fastapi import APIRouter, Depends

from app.http.dependencies import get_current_user, get_user_service
from app.models.user import User
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import (
    ProfileUpdateRequest,
    UserUpdateRequest,
)
from app.schemas.views.user_views import ProfileView, UserView
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserView)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserView:
    """Return the authenticated user's own account."""
    return UserMapper.to_view(current_user)


@router.patch("/me", response_model=UserView)
def update_me(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserView:
    """Update the authenticated user's own account fields."""
    user = user_service.update_me(current_user.uuid, request)
    return UserMapper.to_view(user)


@router.get("/me/profile", response_model=ProfileView)
def get_profile(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ProfileView:
    """Return the authenticated user's health settings."""
    return user_service.get_profile_view(current_user.uuid)


@router.patch("/me/profile", response_model=ProfileView)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ProfileView:
    """Update the authenticated user's health settings."""
    return user_service.update_profile(current_user.uuid, request)
