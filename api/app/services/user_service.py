"""User account and profile business logic."""

import logging
from datetime import date
from uuid import UUID

from app.dao.user_dao import UserDao
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import AuthenticationError, ConflictError, ValidationError
from app.models.user import User
from app.schemas.mappers.user_mapper import UserMapper
from app.schemas.requests.user_requests import (
    ProfileUpdateRequest,
    UserUpdateRequest,
)
from app.schemas.views.user_views import ProfileView
from app.security.passwords import PasswordService
from app.services.zone_reference import current_age, resolve_zone_reference

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
        user = self._user_dao.get_by_uuid(user_id)
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

    def get_profile_view(self, user_id: UUID) -> ProfileView:
        """The caller's health settings as a view (with the active zone reference).

        Returns an empty profile view when no row exists yet.
        """
        profile = self._profile_dao.get(user_id)
        if profile is None:
            return UserMapper.empty_profile_view()
        reference = resolve_zone_reference(profile, date.today())
        return UserMapper.to_profile_view(profile, reference)

    def update_profile(self, user_id: UUID, request: ProfileUpdateRequest) -> ProfileView:
        """Apply a health-settings update and return the resulting view.

        Only fields present in the request body are changed; a field sent as
        ``null`` clears it, an omitted one keeps its current value. Validates
        the resulting date of birth and custom-zone set, creates the profile
        row on first use, commits, and returns the updated view.
        """
        today = date.today()
        current = self._profile_dao.get(user_id)
        provided = request.model_fields_set

        # A field present in the body wins (an explicit null clears it); an
        # omitted field keeps its current value. Written per-field to keep the
        # types explicit and readable.
        max_hr = (
            request.max_heart_rate
            if "max_heart_rate" in provided
            else (current.max_heart_rate if current is not None else None)
        )
        resting_hr = (
            request.resting_heart_rate
            if "resting_heart_rate" in provided
            else (current.resting_heart_rate if current is not None else None)
        )
        date_of_birth = (
            request.date_of_birth
            if "date_of_birth" in provided
            else (current.date_of_birth if current is not None else None)
        )
        cz1 = (
            request.custom_zone_1_top_bpm
            if "custom_zone_1_top_bpm" in provided
            else (current.custom_zone_1_top_bpm if current is not None else None)
        )
        cz2 = (
            request.custom_zone_2_top_bpm
            if "custom_zone_2_top_bpm" in provided
            else (current.custom_zone_2_top_bpm if current is not None else None)
        )
        cz3 = (
            request.custom_zone_3_top_bpm
            if "custom_zone_3_top_bpm" in provided
            else (current.custom_zone_3_top_bpm if current is not None else None)
        )
        cz4 = (
            request.custom_zone_4_top_bpm
            if "custom_zone_4_top_bpm" in provided
            else (current.custom_zone_4_top_bpm if current is not None else None)
        )

        self._validate_date_of_birth(date_of_birth, today)
        self._validate_custom_zones(cz1, cz2, cz3, cz4)

        profile = self._profile_dao.apply_health_settings(
            user_id,
            max_heart_rate=max_hr,
            resting_heart_rate=resting_hr,
            date_of_birth=date_of_birth,
            custom_zone_1_top_bpm=cz1,
            custom_zone_2_top_bpm=cz2,
            custom_zone_3_top_bpm=cz3,
            custom_zone_4_top_bpm=cz4,
        )
        self._unit_of_work.commit()
        logger.info("Updated health settings for %s", user_id)

        reference = resolve_zone_reference(profile, today)
        return UserMapper.to_profile_view(profile, reference)

    @staticmethod
    def _validate_date_of_birth(date_of_birth: date | None, today: date) -> None:
        """Reject a future or implausible birthdate (age must be 1..120)."""
        if date_of_birth is None:
            return
        if date_of_birth > today:
            raise ValidationError("Date of birth cannot be in the future.")
        age = current_age(date_of_birth, today)
        if not 1 <= age <= 120:
            raise ValidationError("Date of birth must be between ages 1 and 120.")

    @staticmethod
    def _validate_custom_zones(
        cz1: int | None, cz2: int | None, cz3: int | None, cz4: int | None
    ) -> None:
        """Custom zones must be a complete, strictly-ascending set of four — or all cleared."""
        if cz1 is not None or cz2 is not None or cz3 is not None or cz4 is not None:
            if cz1 is None or cz2 is None or cz3 is None or cz4 is None:
                raise ValidationError("Provide all four custom zone thresholds, or none.")
            if not (cz1 < cz2 and cz2 < cz3 and cz3 < cz4):
                raise ValidationError("Custom zone thresholds must be strictly ascending.")
