"""User account and profile business logic."""

import logging
from uuid import UUID

from app.dao.user_dao import UserDao
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import AuthenticationError, ConflictError
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import (
    ProfileUpdateRequest,
    UserUpdateRequest,
)
from app.security.passwords import PasswordService

logger = logging.getLogger(__name__)


class UserService:
    """Updates the caller's own account and health settings."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        user_dao: UserDao,
        profile_dao: UserProfileDao,
        password_service: PasswordService,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._user_dao = user_dao
        self._profile_dao = profile_dao
        self._password_service = password_service

    def update_me(self, user_id: UUID, request: UserUpdateRequest) -> User:
        """Apply partial updates to the account.

        Rules:
        * provided name fields replace the current values (trimmed);
        * a provided email is normalized and must not collide with another
          account (ConflictError);
        * a password change requires a correct ``current_password``
          (AuthenticationError when it does not match).
        Commits the session on success.
        """
        user = self._user_dao.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("Account no longer exists.")

        if request.first_name is not None:
            user.first_name = request.first_name.strip()
        if request.last_name is not None:
            user.last_name = request.last_name.strip()

        if request.email is not None:
            email = UserMapper.normalize_email(str(request.email))
            if email != user.email:
                existing = self._user_dao.get_by_email(email)
                if existing is not None:
                    raise ConflictError("This email is already in use.")
                user.email = email

        if request.new_password is not None:
            if request.current_password is None or not self._password_service.verify(
                request.current_password, user.password_hash
            ):
                raise AuthenticationError("Current password is incorrect.")
            user.password_hash = self._password_service.hash(request.new_password)

        self._unit_of_work.commit()
        logger.info("Updated account %s", user_id)
        return user

    def get_profile(self, user_id: UUID) -> UserProfile | None:
        """Return the user's profile row, or None when not set yet."""
        return self._profile_dao.get(user_id)

    def update_profile(self, user_id: UUID, request: ProfileUpdateRequest) -> UserProfile:
        """Update heart-rate settings, keeping values when not provided.

        Creates the profile row on first use. Commits the session.
        """
        current = self._profile_dao.get(user_id)
        max_hr = (
            request.max_heart_rate
            if request.max_heart_rate is not None
            else (current.max_heart_rate if current is not None else None)
        )
        resting_hr = (
            request.resting_heart_rate
            if request.resting_heart_rate is not None
            else (current.resting_heart_rate if current is not None else None)
        )
        profile = self._profile_dao.set_heart_rates(user_id, max_hr, resting_hr)
        self._unit_of_work.commit()
        logger.info("Updated heart-rate settings for %s", user_id)
        return profile
