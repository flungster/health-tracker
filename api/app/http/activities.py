"""Activity routes: import, list, detail, trackpoints, splits, update, delete."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.http.dependencies import (
    get_activity_service,
    get_current_user,
    get_import_service,
    get_sport_service,
)
from app.models.user import User
from app.schemas.mappers.activity_mapper import ActivityMapper
from app.schemas.requests.activity_requests import ActivityUpdateRequest
from app.schemas.views.activity_views import (
    ActivitiesListView,
    ActivityDetailView,
    ActivityPeriodSummaryView,
    SplitsView,
    SportsView,
    SportTypeView,
    TrackpointsView,
)
from app.services.activity_service import ActivityService
from app.services.import_service import ImportService
from app.services.sport_service import SportService

router = APIRouter(prefix="/api/v1", tags=["activities"])


@router.post("/activities", status_code=201, response_model=ActivityDetailView)
def import_activity(
    file: UploadFile = File(...),
    sport_type: str | None = Form(default=None),
    name: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    import_service: ImportService = Depends(get_import_service),
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> ActivityDetailView:
    """Import an activity file (GPX, TCX or FIT) for the current user."""
    # Read at most the limit + 1 byte so an oversized upload is rejected
    # without being buffered in full first.
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    filename = file.filename or "activity"
    activity = import_service.import_activity(
        current_user.uuid,
        filename,
        data,
        sport_override=sport_type,
        name_override=name,
    )
    detail = activity_service.get_detail(current_user.uuid, activity.uuid)
    return ActivityMapper.to_detail_view(*detail)


@router.get("/activities", response_model=ActivitiesListView)
def list_activities(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> ActivitiesListView:
    """The user's activities, newest first, with pagination.

    Unit-bearing values are expressed in the caller's display unit system
    (named by ``units``); metric callers see the stored SI values.
    """
    activities, total, units = activity_service.list_for_user(current_user.uuid, limit, offset)
    return ActivitiesListView(
        items=[ActivityMapper.to_summary_view(activity, units) for activity in activities],
        total=total,
        limit=limit,
        offset=offset,
        units=units.value,
    )


@router.get("/activities/summary", response_model=ActivityPeriodSummaryView)
def activity_period_summary(
    start: str,
    end: str,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> ActivityPeriodSummaryView:
    """Aggregate stats for the user's activities over ``[start, end)`` (dashboard).

    ``start`` / ``end`` are ISO 8601 UTC instants (naive = UTC); the range is
    half-open and ``start`` must precede ``end``. Unit-bearing values follow the
    caller's display unit system (named by ``units``); a metric with no data in
    the period is null, not zero. Declared before the ``{activity_id}`` routes
    so "summary" is not parsed as an activity id.
    """
    summary, units = activity_service.period_summary(current_user.uuid, start, end)
    return ActivityMapper.to_period_summary_view(summary, units)


@router.get("/activities/{activity_id}", response_model=ActivityDetailView)
def get_activity(
    activity_id: UUID,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> ActivityDetailView:
    """Full detail for one of the user's activities."""
    detail = activity_service.get_detail(current_user.uuid, activity_id)
    return ActivityMapper.to_detail_view(*detail)


@router.get("/activities/{activity_id}/trackpoints", response_model=TrackpointsView)
def list_trackpoints(
    activity_id: UUID,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> TrackpointsView:
    """All recorded samples of one of the user's activities.

    ``altitude`` / ``speed`` are expressed in the caller's display unit system
    (named by ``units``); positions never change.
    """
    points, units = activity_service.get_trackpoints(current_user.uuid, activity_id)
    return TrackpointsView(
        items=[ActivityMapper.to_trackpoint_view(point, units) for point in points],
        units=units.value,
    )


@router.get("/activities/{activity_id}/splits", response_model=SplitsView)
def list_splits(
    activity_id: UUID,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> SplitsView:
    """The precomputed splits of one of the user's activities."""
    detail = activity_service.get_detail(current_user.uuid, activity_id)
    return SplitsView(items=[ActivityMapper.to_split_view(split) for split in detail[1]])


@router.patch("/activities/{activity_id}", response_model=ActivityDetailView)
def update_activity(
    activity_id: UUID,
    request: ActivityUpdateRequest,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> ActivityDetailView:
    """Update name, description and/or sport of one of the user's activities."""
    activity_service.update_for_user(
        current_user.uuid,
        activity_id,
        name=request.name,
        description=request.description,
        sport_type=request.sport_type,
    )
    detail = activity_service.get_detail(current_user.uuid, activity_id)
    return ActivityMapper.to_detail_view(*detail)


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: UUID,
    activity_service: ActivityService = Depends(get_activity_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Soft-delete one of the user's activities."""
    activity_service.delete_for_user(current_user.uuid, activity_id)
    return Response(status_code=204)


@router.get("/sports", response_model=SportsView)
def list_sports(sport_service: SportService = Depends(get_sport_service)) -> SportsView:
    """The canonical list of sport types (for pickers in the UI)."""
    types = sport_service.list_types()
    return SportsView(
        sports=[SportTypeView(value=t.value, description=t.description) for t in types]
    )
