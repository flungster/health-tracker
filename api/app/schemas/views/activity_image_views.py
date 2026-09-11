"""View schemas for activity images."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivityImageView(BaseModel):
    """One image attached to an activity.

    ``id`` is the row's public uuid (identifier convention); image bytes are
    fetched separately from ``GET /activities/{id}/images/{image_id}``.
    """

    id: UUID
    source: str  # e.g. "uploaded"
    original_filename: str | None
    bytes: int
    created_at: datetime


class ActivityImagesView(BaseModel):
    """All live images of one activity, in upload order."""

    items: list[ActivityImageView]
