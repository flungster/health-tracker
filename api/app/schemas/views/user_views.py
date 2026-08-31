"""View schemas for user accounts and authentication.

Views are the only representation of models that leaves the API.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class UserView(BaseModel):
    """Public representation of a user account."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    created_at: datetime


class AuthResponseView(BaseModel):
    """Response for register/login: the account plus a session token."""

    user: UserView
    token: str


class ProfileView(BaseModel):
    """Public representation of per-user health settings.

    The first block is the stored configuration; ``zone_source`` /
    ``effective_max_heart_rate`` / ``age`` are computed (not stored) and name
    the zone reference currently in effect, so a client can show "zones are
    computed from …" without re-implementing the precedence.
    """

    max_heart_rate: int | None
    resting_heart_rate: int | None
    date_of_birth: date | None
    custom_zone_1_top_bpm: int | None
    custom_zone_2_top_bpm: int | None
    custom_zone_3_top_bpm: int | None
    custom_zone_4_top_bpm: int | None

    # Computed from the stored settings (see app.services.zone_reference).
    zone_source: str | None  # "custom" / "max_heart_rate" / "age", or null
    effective_max_heart_rate: int | None  # the max HR used, for age/max_heart_rate
    age: int | None  # current derived age (from date_of_birth), for display
