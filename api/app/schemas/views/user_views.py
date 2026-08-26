"""View schemas for user accounts and authentication.

Views are the only representation of models that leaves the API.
"""

from datetime import datetime
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
    """Public representation of per-user health settings."""

    max_heart_rate: int | None
    resting_heart_rate: int | None
