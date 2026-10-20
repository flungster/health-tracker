"""View schemas for activity images."""

from uuid import UUID

from pydantic import BaseModel

from app.schemas.views.utc_datetime import UtcDateTime


class ActivityImageView(BaseModel):
    """One image attached to an activity.

    ``id`` is the row's public uuid (identifier convention); image bytes are
    fetched separately from ``GET /activities/{id}/images/{image_id}``.
    """

    id: UUID
    source: str  # e.g. "uploaded"
    original_filename: str | None
    bytes: int
    created_at: UtcDateTime


class ActivityImagesView(BaseModel):
    """All live images of one activity, in upload order."""

    items: list[ActivityImageView]
