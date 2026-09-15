"""Request schemas for activities."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ActivityUpdateRequest(BaseModel):
    """Body for PATCH /api/v1/activities/{id}.

    Only the provided fields are changed; at least one is required.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sport_type: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ActivityUpdateRequest":
        if self.name is None and self.description is None and self.sport_type is None:
            raise ValueError("Provide at least one field to update.")
        return self


class DuplicateLinkRequest(BaseModel):
    """Body for POST /api/v1/activities/{id}/duplicates (M28a).

    ``duplicate_of`` names the recognized primary. With ``make_primary``,
    instead: this activity goes live and ``duplicate_of`` becomes ITS duplicate.
    """

    duplicate_of: UUID = Field(description="The activity this one is a duplicate of.")
    make_primary: bool = False


class DuplicateOverwriteRequest(BaseModel):
    """Body for POST /api/v1/activities/{id}/duplicates/overwrite (M28a).

    Confirmed same-workout re-import: this activity replaces ``duplicate_of``,
    which is soft-deleted (kept for history and rollback).
    """

    duplicate_of: UUID = Field(description="The older activity to replace (soft-deleted).")
