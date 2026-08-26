"""Data access for per-user health settings."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.user_profile import UserProfile


class UserProfileDao(IntIdDao[UserProfile]):
    """Reads and writes of the ``user_profiles`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, UserProfile)

    def get(self, user_id: UUID) -> UserProfile | None:
        """Fetch the active profile for a user, or None."""
        statement = select(UserProfile).where(
            UserProfile.user_id == user_id,
            UserProfile.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def add(self, profile: UserProfile) -> UserProfile:
        """Persist a new profile. The caller commits the session."""
        self.session.add(profile)
        self.session.flush()
        return profile

    def set_heart_rates(
        self,
        user_id: UUID,
        max_heart_rate: int | None,
        resting_heart_rate: int | None,
    ) -> UserProfile:
        """Set heart-rate settings, creating the profile when missing."""
        profile = self.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.session.add(profile)
        profile.max_heart_rate = max_heart_rate
        profile.resting_heart_rate = resting_heart_rate
        self.session.flush()
        return profile
