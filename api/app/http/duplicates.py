"""Activity duplicate routes (M28a): detect, link, unlink, overwrite.

Linked duplicates stay stored and reachable by their own URL; while linked they
are excluded from feeds, counts and dashboard aggregates. Every operation is
reversible — nothing here hard-deletes anything (overwrite soft-deletes, like a
normal delete).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.http.dependencies import get_current_user, get_duplicate_service
from app.models.user import User
from app.schemas.mappers.activity_mapper import ActivityMapper
from app.schemas.requests.activity_requests import (
    DuplicateLinkRequest,
    DuplicateOverwriteRequest,
)
from app.schemas.views.activity_views import DuplicateActivitiesView
from app.services.duplicate_service import DuplicateService

router = APIRouter(prefix="/api/v1", tags=["activities"])


@router.get(
    "/activities/{activity_id}/duplicate-candidates", response_model=DuplicateActivitiesView
)
def list_duplicate_candidates(
    activity_id: UUID,
    duplicate_service: DuplicateService = Depends(get_duplicate_service),
    current_user: User = Depends(get_current_user),
) -> DuplicateActivitiesView:
    """The caller's live activities that look like the same workout as this one.

    Heuristic and conservative (same sport, start within 30 minutes, duration
    or distance aligned); strongest match first. A suggestion for a human — the
    API never acts on it automatically (bulk provider sync is the exception:
    it links and reports, see ``SyncResultView.linked_duplicates``).
    """
    activities, units = duplicate_service.find_candidates(current_user.uuid, activity_id)
    return DuplicateActivitiesView(
        items=[ActivityMapper.to_summary_view(activity, units) for activity in activities],
        units=units.value,
    )


@router.get("/activities/{activity_id}/duplicates", response_model=DuplicateActivitiesView)
def list_linked_duplicates(
    activity_id: UUID,
    duplicate_service: DuplicateService = Depends(get_duplicate_service),
    current_user: User = Depends(get_current_user),
) -> DuplicateActivitiesView:
    """The caller's activities linked as duplicates of this one (its feed row)."""
    activities, units = duplicate_service.list_linked_duplicates(current_user.uuid, activity_id)
    return DuplicateActivitiesView(
        items=[ActivityMapper.to_summary_view(activity, units) for activity in activities],
        units=units.value,
    )


@router.post("/activities/{activity_id}/duplicates", status_code=204)
def link_duplicate(
    activity_id: UUID,
    request: DuplicateLinkRequest,
    duplicate_service: DuplicateService = Depends(get_duplicate_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """Link this activity as a duplicate of ``duplicate_of`` (or swap with make_primary)."""
    duplicate_service.link(
        current_user.uuid, activity_id, request.duplicate_of, request.make_primary
    )


@router.delete("/activities/{activity_id}/duplicates", status_code=204)
def unlink_duplicate(
    activity_id: UUID,
    duplicate_service: DuplicateService = Depends(get_duplicate_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """Clear the link; this activity becomes a live (primary) activity again."""
    duplicate_service.unlink(current_user.uuid, activity_id)


@router.post("/activities/{activity_id}/duplicates/overwrite", status_code=204)
def overwrite_duplicate(
    activity_id: UUID,
    request: DuplicateOverwriteRequest,
    duplicate_service: DuplicateService = Depends(get_duplicate_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """Confirmed re-import of the same workout from one source: replace ``duplicate_of``.

    The replaced activity is soft-deleted (kept for history and rollback), so
    a wrong confirmation costs an undo, not the data.
    """
    duplicate_service.overwrite(current_user.uuid, activity_id, request.duplicate_of)
