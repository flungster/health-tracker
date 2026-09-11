"""Business logic for activity images: upload, list, serve and delete.

The image bytes live on disk under ``uploads/<user_id>/images/`` (mirroring
the import file layout); the database row is the authoritative record. Every
read/write path is scoped to the caller through the activity's ownership.

The on-disk format is decided by the file's magic bytes, not its extension:
a renamed non-image is rejected at upload time and can never be served as an
image later.
"""

import logging
from pathlib import Path
from uuid import UUID

from app.config import Settings
from app.dao.activity_dao import ActivityDao
from app.dao.activity_image_dao import ActivityImageDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.models.activity import Activity
from app.models.activity_image import ActivityImage
from app.schemas.mappers.activity_image_mapper import (
    ActivityImageMapper,
)

logger = logging.getLogger(__name__)

#: Allowed upload extensions -> media type. The extension is a display-side
#: gate; the magic bytes decide what actually gets stored (see _validate).
IMAGE_EXTENSIONS: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

#: One canonical on-disk extension per media type (files are stored as the
#: row's ``stored_name`` = uuid + this extension).
CANONICAL_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

#: Magic-byte prefixes identifying the allowed formats.
_JPEG_PREFIX = b"\xff\xd8\xff"
_PNG_PREFIX = b"\x89PNG\r\n\x1a\n"


def sniff_image_media_type(data: bytes) -> str | None:
    """The media type of an image's magic bytes, or None when not one."""
    if data.startswith(_JPEG_PREFIX):
        return "image/jpeg"
    if data.startswith(_PNG_PREFIX):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class ActivityImageService:
    """Upload, list, serve and delete the photos attached to an activity."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        image_dao: ActivityImageDao,
        activity_dao: ActivityDao,
        settings: Settings,
    ) -> None:
        self._uow = unit_of_work
        self._image_dao = image_dao
        self._activity_dao = activity_dao
        self._settings = settings

    def upload(
        self, user_id: UUID, activity_uuid: UUID, filename: str | None, data: bytes
    ) -> ActivityImage:
        """Store one photo for the caller's activity and record it."""
        self._require_activity(user_id, activity_uuid)
        media_type = self._validate(filename, data)

        suffix = CANONICAL_EXTENSIONS[media_type]
        image = ActivityImageMapper.from_upload(activity_uuid, filename, len(data), suffix)
        self._image_dao.add(image)

        path = self._file_path(user_id, image.stored_name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as error:
            raise ValidationError(f"Could not store the image file: {error}") from error

        try:
            self._uow.commit()
        except Exception:
            # The row did not land; do not leave an orphan file behind.
            path.unlink(missing_ok=True)
            self._uow.rollback()
            raise
        return image

    def list_for_user(self, user_id: UUID, activity_uuid: UUID) -> list[ActivityImage]:
        """The caller's activity images in upload order."""
        self._require_activity(user_id, activity_uuid)
        return self._image_dao.list_for_activity(activity_uuid)

    def serve(self, user_id: UUID, activity_uuid: UUID, image_uuid: UUID) -> tuple[bytes, str]:
        """The bytes and media type of a live image (for the serve endpoint).

        Raises NotFoundError when the image does not exist, belongs to a
        different activity, is deleted, or its file is missing on disk.
        """
        self._require_activity(user_id, activity_uuid)
        image = self._live_image(activity_uuid, image_uuid)

        path = self._file_path(user_id, image.stored_name)
        if not path.is_file():
            raise NotFoundError("Image file is missing.")
        media_type = IMAGE_EXTENSIONS.get(path.suffix.lower())
        if media_type is None:  # stored_name always carries a validated extension; belt and braces
            raise NotFoundError("Image file is missing.")
        return path.read_bytes(), media_type

    def delete_for_user(self, user_id: UUID, activity_uuid: UUID, image_uuid: UUID) -> None:
        """Soft-delete an image and remove its file from disk.

        The row is the authoritative record, so it commits first; removing
        the bytes afterwards is best-effort (a failure only logs — the image
        is already gone from every view).
        """
        self._require_activity(user_id, activity_uuid)
        image = self._live_image(activity_uuid, image_uuid)

        self._image_dao.soft_delete(image)
        try:
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            raise

        path = self._file_path(user_id, image.stored_name)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning("Could not remove image file %s: %s", path, error)

    def _require_activity(self, user_id: UUID, activity_uuid: UUID) -> Activity:
        """The caller's own activity or a 404 (someone else's reads as missing)."""
        activity = self._activity_dao.get_by_uuid(activity_uuid)
        if activity is None or activity.user_id != user_id:
            raise NotFoundError("Activity not found.")
        return activity

    def _live_image(self, activity_uuid: UUID, image_uuid: UUID) -> ActivityImage:
        """A non-deleted image of the given activity, or a 404."""
        image = self._image_dao.get_by_uuid(image_uuid)
        if image is None or image.deleted_at is not None or image.activity_id != activity_uuid:
            raise NotFoundError("Image not found.")
        return image

    def _validate(self, filename: str | None, data: bytes) -> str:
        """Shared upload checks; returns the sniffed media type on success."""
        suffix = Path(filename or "image").suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise ValidationError("Unsupported image type. Upload a JPEG, PNG or WebP file.")
        if len(data) == 0:
            raise ValidationError("Image file is empty.")
        max_bytes = self._settings.max_upload_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValidationError(
                f"Image exceeds the maximum upload size of {self._settings.max_upload_mb} MB."
            )
        media_type = sniff_image_media_type(data)
        if media_type is None:
            raise ValidationError("File is not a valid image (JPEG, PNG or WebP).")
        return media_type

    def _file_path(self, user_id: UUID, stored_name: str) -> Path:
        """The on-disk location of an image's bytes."""
        return Path(self._settings.uploads_dir) / str(user_id) / "images" / stored_name
