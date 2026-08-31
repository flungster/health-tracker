"""Request schemas for user accounts and authentication."""

from datetime import date

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Body for POST /api/v1/auth/register."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Body for POST /api/v1/auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdateRequest(BaseModel):
    """Body for PATCH /api/v1/users/me.

    Only the provided fields are changed. Changing the password requires
    both ``current_password`` and ``new_password``.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    """Body for PATCH /api/v1/users/me/profile.

    Only the fields present in the body are changed; a field sent as ``null``
    clears it (an omitted field keeps its current value). Heart rates and zone
    thresholds are in bpm. Custom zones must be sent as a complete, strictly-
    ascending set of four (or all cleared); validation is enforced in the
    service so clients get the app error envelope.
    """

    max_heart_rate: int | None = Field(default=None, ge=30, le=300)
    resting_heart_rate: int | None = Field(default=None, ge=30, le=300)
    date_of_birth: date | None = Field(default=None)
    custom_zone_1_top_bpm: int | None = Field(default=None, ge=30, le=300)
    custom_zone_2_top_bpm: int | None = Field(default=None, ge=30, le=300)
    custom_zone_3_top_bpm: int | None = Field(default=None, ge=30, le=300)
    custom_zone_4_top_bpm: int | None = Field(default=None, ge=30, le=300)
