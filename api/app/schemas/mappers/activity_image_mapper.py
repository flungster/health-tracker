"""Mapping between activity image models and API views."""

from uuid import UUID, uuid4

from app.models.activity_image import ActivityImage
from app.schemas.views.activity_image_views import (
    ActivityImageView,
)


class ActivityImageMapper:
    """Explicit model <-> view conversion for activity images."""

    @staticmethod
    def from_upload(
        activity_id: UUID, original_filename: str | None, byte_size: int, suffix: str
    ) -> ActivityImage:
        """A new image row for a user upload (M22b).

        ``suffix`` is the canonical on-disk extension for the validated media
        type (e.g. ``".jpg"``); it names the stored file alongside the uuid.
        The source is always ``uploaded`` today; provider fetches will get
        their own factory when the Strava half of M22 ships.
        """
        image_uuid = uuid4()
        return ActivityImage(
            uuid=image_uuid,
            activity_id=activity_id,
            source="uploaded",
            original_filename=original_filename,
            stored_name=f"{image_uuid}{suffix}",
            bytes=byte_size,
        )

    @staticmethod
    def to_view(image: ActivityImage) -> ActivityImageView:
        """The public view of one image row."""
        return ActivityImageView(
            id=image.uuid,
            source=image.source,
            original_filename=image.original_filename,
            bytes=image.bytes,
            created_at=image.created_at,
        )
