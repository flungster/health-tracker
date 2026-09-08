"""Mapping between user requests, ORM models, and API views."""

from uuid import uuid4

from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.units import units_for
from app.schemas.views.user_views import ProfileView, UserView
from app.services.zone_reference import ZoneReference


class UserMapper:
    """Translates user data between the three representation layers."""

    @staticmethod
    def normalize_email(email: str) -> str:
        """Trim padding and lowercase so email is case-insensitive."""
        return email.strip().lower()

    @staticmethod
    def create_user(
        first_name: str,
        last_name: str,
        email_normalized: str,
        password_hash: str,
    ) -> User:
        """Build a new User model (public uuid generated here, not in the DB)."""
        return User(
            uuid=uuid4(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email_normalized,
            password_hash=password_hash,
        )

    @staticmethod
    def to_view(user: User) -> UserView:
        """Map an ORM user to its public view."""
        return UserView(
            id=user.uuid,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            created_at=user.created_at,
        )

    @staticmethod
    def units_system_for(profile: UserProfile | None) -> str:
        """The display unit system for a profile (delegates to app.schemas.units).

        Derived from ``imperial_units_enabled_at``: set = imperial (in effect
        since that instant), unset or no profile row = metric. Always one of
        the two system strings, never null.
        """
        instant = profile.imperial_units_enabled_at if profile is not None else None
        return units_for(instant).value

    @staticmethod
    def to_profile_view(profile: UserProfile, reference: ZoneReference | None) -> ProfileView:
        """Map an ORM profile (plus its resolved zone reference) to a view."""
        return ProfileView(
            max_heart_rate=profile.max_heart_rate,
            resting_heart_rate=profile.resting_heart_rate,
            date_of_birth=profile.date_of_birth,
            custom_zone_1_top_bpm=profile.custom_zone_1_top_bpm,
            custom_zone_2_top_bpm=profile.custom_zone_2_top_bpm,
            custom_zone_3_top_bpm=profile.custom_zone_3_top_bpm,
            custom_zone_4_top_bpm=profile.custom_zone_4_top_bpm,
            zone_source=(reference.source.value if reference is not None else None),
            effective_max_heart_rate=reference.max_heart_rate if reference is not None else None,
            age=(reference.age if reference is not None else None),
            units_system=UserMapper.units_system_for(profile),
        )

    @staticmethod
    def empty_profile_view() -> ProfileView:
        """View for a user who has no profile row yet."""
        return ProfileView(
            max_heart_rate=None,
            resting_heart_rate=None,
            date_of_birth=None,
            custom_zone_1_top_bpm=None,
            custom_zone_2_top_bpm=None,
            custom_zone_3_top_bpm=None,
            custom_zone_4_top_bpm=None,
            zone_source=None,
            effective_max_heart_rate=None,
            age=None,
            units_system="metric",  # no profile row -> the default system
        )
