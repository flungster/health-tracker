"""Mapping between user requests, ORM models, and API views."""

from uuid import uuid4

from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.views.user_views import ProfileView, UserView


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
    def to_profile_view(profile: UserProfile) -> ProfileView:
        """Map an ORM profile to its public view."""
        return ProfileView(
            max_heart_rate=profile.max_heart_rate,
            resting_heart_rate=profile.resting_heart_rate,
        )

    @staticmethod
    def empty_profile_view() -> ProfileView:
        """View for a user who has no profile row yet."""
        return ProfileView(max_heart_rate=None, resting_heart_rate=None)
