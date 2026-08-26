"""Request schemas for user accounts and authentication."""

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

    Only the provided fields are changed. Heart rates are in bpm.
    """

    max_heart_rate: int | None = Field(default=None, ge=30, le=300)
    resting_heart_rate: int | None = Field(default=None, ge=30, le=300)
