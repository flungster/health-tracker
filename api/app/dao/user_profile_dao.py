"""Data access for per-user health settings."""

from datetime import date
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

    def apply_health_settings(
        self,
        user_id: UUID,
        *,
        max_heart_rate: int | None,
        resting_heart_rate: int | None,
        date_of_birth: date | None,
        custom_zone_1_top_bpm: int | None,
        custom_zone_2_top_bpm: int | None,
        custom_zone_3_top_bpm: int | None,
        custom_zone_4_top_bpm: int | None,
    ) -> UserProfile:
        """Write the full resolved health-settings state.

        The caller (service) has already merged provided values over current
        ones, so this simply persists the resulting state — a ``None`` here is
        a deliberate clear. Creates the profile row when missing; flushes, and
        the caller commits.
        """
        profile = self.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.session.add(profile)
        profile.max_heart_rate = max_heart_rate
        profile.resting_heart_rate = resting_heart_rate
        profile.date_of_birth = date_of_birth
        profile.custom_zone_1_top_bpm = custom_zone_1_top_bpm
        profile.custom_zone_2_top_bpm = custom_zone_2_top_bpm
        profile.custom_zone_3_top_bpm = custom_zone_3_top_bpm
        profile.custom_zone_4_top_bpm = custom_zone_4_top_bpm
        self.session.flush()
        return profile
