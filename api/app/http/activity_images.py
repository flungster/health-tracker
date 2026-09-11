"""Activity image routes: upload, list, serve and delete photos."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.http.dependencies import (
    get_activity_image_service,
    get_current_user,
)
from app.models.user import User
from app.schemas.mappers.activity_image_mapper import ActivityImageMapper
from app.schemas.views.activity_image_views import (
    ActivityImagesView,
    ActivityImageView,
)
from app.services.activity_image_service import (
    ActivityImageService,
)

router = APIRouter(prefix="/api/v1", tags=["activities"])


@router.post("/activities/{activity_id}/images", status_code=201, response_model=ActivityImageView)
def upload_image(
    activity_id: UUID,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    image_service: ActivityImageService = Depends(get_activity_image_service),
    current_user: User = Depends(get_current_user),
) -> ActivityImageView:
    """Attach one photo (JPEG, PNG or WebP) to the caller's activity."""
    # Read at most the limit + 1 byte so an oversized upload is rejected
    # without being buffered in full first (same pattern as activity import).
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    image = image_service.upload(current_user.uuid, activity_id, file.filename or "image", data)
    return ActivityImageMapper.to_view(image)


@router.get("/activities/{activity_id}/images", response_model=ActivityImagesView)
def list_images(
    activity_id: UUID,
    image_service: ActivityImageService = Depends(get_activity_image_service),
    current_user: User = Depends(get_current_user),
) -> ActivityImagesView:
    """The caller's activity images in upload order."""
    images = image_service.list_for_user(current_user.uuid, activity_id)
    return ActivityImagesView(items=[ActivityImageMapper.to_view(image) for image in images])


@router.get("/activities/{activity_id}/images/{image_id}")
def serve_image(
    activity_id: UUID,
    image_id: UUID,
    image_service: ActivityImageService = Depends(get_activity_image_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    """The image bytes, authenticated (header or session cookie — M22a)."""
    data, media_type = image_service.serve(current_user.uuid, activity_id, image_id)
    return Response(content=data, media_type=media_type)


@router.delete("/activities/{activity_id}/images/{image_id}", status_code=204, response_model=None)
def delete_image(
    activity_id: UUID,
    image_id: UUID,
    image_service: ActivityImageService = Depends(get_activity_image_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete one of the caller's activity images (file removed from disk)."""
    image_service.delete_for_user(current_user.uuid, activity_id, image_id)
