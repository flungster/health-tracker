"""Linked-duplicate operations (M28a): find, link, unlink, overwrite.

A linked duplicate is a visibility decision, not data loss: the row stays
stored and reachable by its own URL (``ActivityDao.get_for_user``), but drops
out of feeds, counts and dashboard aggregates while ``duplicate_of`` is set.
All operations are reversible — unlinking or swapping makes a row live again,
and overwrite (the same-source "replace the old import" path) soft-deletes its
target like any other delete.

The matcher itself is :mod:`app.services.duplicate_detection` (pure). This
service owns the user-scoped query that supplies candidates and the invariants:

* an activity cannot be its own duplicate;
* you can only link to a **live, unlinked** activity of your own — linking a
  duplicate to another duplicate would create depth-2 chains, which the query
  layer does not support (a list-style filter is a single-column check);
* everything the user owns, nothing else.
"""

from datetime import timedelta
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.user_profile_dao import UserProfileDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError, ValidationError
from app.models.activity import Activity
from app.schemas.units import UnitSystem, units_for
from app.services.duplicate_detection import (
    TIME_TOLERANCE_SECONDS,
    DuplicateSignals,
    find_duplicates,
)


def signals_from_activity(activity: Activity) -> DuplicateSignals:
    """The matcher's view of a stored row (UTC epoch seconds, timezone-free)."""
    started = activity.started_at.timestamp()
    return DuplicateSignals(
        sport_type=activity.sport_type,
        started_at_utc_seconds=float(started),
        duration_seconds=activity.duration_seconds or None,
        distance_m=activity.distance_m,
    )


class DuplicateService:
    """Cross-source duplicate detection + linking for the caller's activities."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        activity_dao: ActivityDao,
        profile_dao: UserProfileDao,
    ) -> None:
        self._uow = unit_of_work
        self._activity_dao = activity_dao
        self._profile_dao = profile_dao

    def _units_for(self, user_id: UUID) -> UnitSystem:
        """The caller's display unit system (metric when there is no profile)."""
        profile = self._profile_dao.get(user_id)
        return units_for(profile.imperial_units_enabled_at if profile is not None else None)

    def _require_activity(self, user_id: UUID, activity_uuid: UUID) -> Activity:
        """The caller's own live activity or a 404 (someone else's reads as missing)."""
        activity = self._activity_dao.get_for_user(user_id, activity_uuid)
        if activity is None:
            raise NotFoundError("Activity not found.")
        return activity

    def find_candidates(
        self, user_id: UUID, activity_uuid: UUID
    ) -> tuple[list[Activity], UnitSystem]:
        """The user's live primaries that look like the same workout as ``activity_uuid``.

        The activity itself is never a candidate (it may already be linked —
        re-running detection on its own row would match itself). Candidates are
        strongest-first (closest start time); the client presents them for a
        human decision, it never acts on this list automatically.
        """
        activity = self._require_activity(user_id, activity_uuid)
        window_start = activity.started_at - timedelta(seconds=TIME_TOLERANCE_SECONDS)
        window_end = activity.started_at + timedelta(seconds=TIME_TOLERANCE_SECONDS)
        pool = self._activity_dao.live_primaries_in_window(
            user_id, activity.sport_type, window_start, window_end
        )
        pool = [candidate for candidate in pool if candidate.uuid != activity.uuid]
        matches = find_duplicates(
            signals_from_activity(activity), [signals_from_activity(c) for c in pool]
        )
        return [pool[match.index] for match in matches], self._units_for(user_id)

    def list_linked_duplicates(
        self, user_id: UUID, primary_uuid: UUID
    ) -> tuple[list[Activity], UnitSystem]:
        """The user's live activities linked as duplicates of ``primary_uuid``."""
        self._require_activity(user_id, primary_uuid)
        return (
            self._activity_dao.list_linked_duplicates_for_user(user_id, primary_uuid),
            self._units_for(user_id),
        )

    def link(
        self, user_id: UUID, activity_uuid: UUID, primary_uuid: UUID, make_primary: bool
    ) -> None:
        """Link ``activity_uuid`` as a duplicate of ``primary_uuid`` (or swap).

        With ``make_primary``, the two roles exchange: this row becomes live
        and the target becomes its duplicate (both writes commit as one).
        """
        activity = self._require_activity(user_id, activity_uuid)
        if primary_uuid == activity.uuid:
            raise ValidationError("An activity cannot be a duplicate of itself.")
        primary = self._require_activity(user_id, primary_uuid)

        if not make_primary:
            self._assert_linkable(primary)

        if make_primary:
            # The target becomes this row's duplicate; this row goes live. All
            # writes flush in the same transaction — a swap is all-or-nothing.
            activity.duplicate_of = None
            primary.duplicate_of = activity.uuid
            # Aliases that pointed at the old target follow it to the new
            # primary, so depth stays at one (no alias-of-an-alias chains).
            for follower in self._activity_dao.list_linked_duplicates_for_user(
                user_id, primary.uuid
            ):
                follower.duplicate_of = activity.uuid
        else:
            if activity.duplicate_of == primary_uuid:
                return  # already linked exactly like this; a no-op keeps retries safe
            activity.duplicate_of = primary.uuid

        self._uow.commit()

    def unlink(self, user_id: UUID, activity_uuid: UUID) -> None:
        """Clear the link; ``activity_uuid`` becomes a live activity again."""
        activity = self._require_activity(user_id, activity_uuid)
        if activity.duplicate_of is None:
            raise ValidationError("This activity is not a linked duplicate.")
        activity.duplicate_of = None
        self._uow.commit()

    def overwrite(self, user_id: UUID, replacing_uuid: UUID, replaced_uuid: UUID) -> None:
        """Replace ``replaced_uuid`` with ``replacing_uuid`` (the confirmed re-import).

        The replaced row is soft-deleted like any other delete — kept for
        history and rollback. Both rows must be the caller's own and live; a
        human already confirmed they are the same workout, so no field-tuple
        check is imposed here (re-imports after a parser fix legitimately differ).
        """
        replacing = self._require_activity(user_id, replacing_uuid)
        replaced = self._require_activity(user_id, replaced_uuid)
        if replacing.uuid == replaced.uuid:
            raise ValidationError("An activity cannot replace itself.")
        self._activity_dao.soft_delete(replaced)
        # If the replaced row had duplicates linked to it, they now point at a
        # deleted primary: clear them so nothing dangles (they become live).
        for orphan in self._activity_dao.list_linked_duplicates_for_user(user_id, replaced.uuid):
            orphan.duplicate_of = None
        self._uow.commit()

    def _assert_linkable(self, target: Activity) -> None:
        """A link target must be a live primary — never a duplicate itself (depth ≤ 1)."""
        if target.duplicate_of is not None:
            raise ValidationError("Cannot link to an activity that is itself a linked duplicate.")
