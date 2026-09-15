"""Provider sync: pull a connected user's activities from their provider.

A sync run walks the provider's activity list from the stored cursor (the
walk goes newest -> older, one page per adapter call) and imports every
activity not imported before — deduped by the global
``(provider, external_activity_id)`` index, so re-syncing only pulls what is
new. The cursor is checkpointed after each full page, so an interrupted or
rate-limited run resumes where it stopped; a run that finishes the walk
clears the cursor.

Every run is bounded below by an import-from floor: the request's ``since``
when given, else the connection's saved ``sync_since``, else no floor (full
history). The floor is the walk's only boundary — the provider is asked for
activities started at or after it on every page.

Provider failures surface as ``ProviderUpstreamError`` (502); a rate limit
carries ``retry_after_seconds`` (the response gets a ``Retry-After`` header).
"""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.provider_account_dao import ProviderAccountDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError
from app.models.activity import Activity
from app.models.provider_account import ProviderAccount
from app.providers.base import ProviderAdapter, ProviderCredentials
from app.providers.registry import ProviderRegistry
from app.schemas.views.provider_views import SyncResultView
from app.services.duplicate_detection import TIME_TOLERANCE_SECONDS, find_duplicates
from app.services.duplicate_service import signals_from_activity
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)

#: Most list pages fetched in one sync run. A run that hits the cap keeps its
#: cursor; the next run resumes. Bounds the time a single request can hold.
MAX_SYNC_PAGES = 25
#: Refresh the access token this far before its expiry (avoid races at the edge).
TOKEN_REFRESH_BUFFER = timedelta(seconds=60)


class ProviderSyncService:
    """Syncs one user's activities from one of their connected providers."""

    def __init__(
        self,
        unit_of_work: UnitOfWork,
        account_dao: ProviderAccountDao,
        activity_dao: ActivityDao,
        registry: ProviderRegistry,
        import_service: ImportService,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._account_dao = account_dao
        self._activity_dao = activity_dao
        self._registry = registry
        self._import_service = import_service

    def sync(self, user_uuid: UUID, provider: str, since: date | None = None) -> SyncResultView:
        """Run one sync. Commits per imported activity and per cursor page.

        ``since`` (an ISO 8601 date, UTC midnight) overrides the
        connection's saved import-from floor for this run only. Raises
        NotFoundError when there is no active connection (or the provider is
        unknown/unconfigured) and ProviderUpstreamError when the provider
        fails (with ``retry_after_seconds`` on a rate limit).
        """
        account = self._account_dao.get_for_user(user_uuid, provider)
        if account is None:
            raise NotFoundError(f"No {provider} connection to sync.")
        adapter = self._registry.get(provider)
        access_token = self._ensure_access_token(adapter, account)
        start_date = self._floor_to_unix(since, account.sync_since)

        cursor = account.sync_cursor
        imported = 0
        skipped = 0
        linked_duplicates = 0
        walk_complete = False
        pages = 0
        while True:
            pages += 1
            page = adapter.fetch_activity_ids(access_token, cursor, start_date=start_date)
            for external_id in page.external_activity_ids:
                if self._activity_dao.exists_for_provider(provider, external_id):
                    skipped += 1
                    continue
                parsed = adapter.fetch_activity(access_token, external_id)
                activity = self._import_service.import_parsed(
                    user_uuid,
                    parsed,
                    provider=provider,
                    external_activity_id=external_id,
                )
                imported += 1
                # Cross-source duplicate (M28a): the same workout may already be
                # in health-tracker from another source (an upload, or a later
                # second provider). Bulk sync never prompts — it links the new
                # row to the existing primary, which is safe because linking is
                # reversible and reported here. Same-provider redeliveries can't
                # reach this point (the external-id dedup above skips them).
                linked = self._link_cross_source_duplicate(user_uuid, activity)
                if linked:
                    linked_duplicates += 1
            if page.next_cursor is None:
                walk_complete = True
                break
            cursor = page.next_cursor
            account.sync_cursor = cursor
            self._unit_of_work.commit()
            if pages >= MAX_SYNC_PAGES:
                logger.info(
                    "%s sync for user %s paused after %d pages; resumes next run",
                    provider,
                    user_uuid,
                    pages,
                )
                break

        if walk_complete:
            account.sync_cursor = None
        account.last_sync_at = datetime.now(UTC)
        self._unit_of_work.commit()
        logger.info(
            "%s sync for user %s: %d imported, %d skipped, %d linked as duplicates "
            "(%d pages, floor %s)",
            provider,
            user_uuid,
            imported,
            skipped,
            linked_duplicates,
            pages,
            start_date,
        )
        return SyncResultView(
            imported=imported,
            skipped=skipped,
            linked_duplicates=linked_duplicates,
            last_sync_at=account.last_sync_at,
        )

    def _link_cross_source_duplicate(self, user_uuid: UUID, activity: Activity) -> bool:
        """Link a just-imported row to an existing primary when the match is clear.

        Returns True (and commits) when a candidate was found — the strongest
        one, i.e. the closest start time; existing rows always win over newly
        imported ones (health-tracker's copy stays the one that shows).
        """
        window = timedelta(seconds=TIME_TOLERANCE_SECONDS)
        pool = self._activity_dao.live_primaries_in_window(
            user_uuid,
            activity.sport_type,
            activity.started_at - window,
            activity.started_at + window,
        )
        pool = [candidate for candidate in pool if candidate.uuid != activity.uuid]
        matches = find_duplicates(
            signals_from_activity(activity), [signals_from_activity(c) for c in pool]
        )
        if not matches:
            return False
        activity.duplicate_of = pool[matches[0].index].uuid
        self._unit_of_work.commit()
        return True

    @staticmethod
    def _floor_to_unix(since: date | None, saved_floor: datetime | None) -> int | None:
        """The walk's lower bound as a unix timestamp, or None (no floor).

        Precedence: the request's ``since`` wins, then the connection's
        saved ``sync_since`` (a user preference), then no floor.
        """
        if since is not None:
            return int(datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp())
        if saved_floor is not None:
            return int(saved_floor.timestamp())
        return None

    def _ensure_access_token(self, adapter: ProviderAdapter, account: ProviderAccount) -> str:
        """A usable access token, refreshing (and persisting the rotation)
        when the cached one is expired or about to be."""
        if account.token_expires_at - datetime.now(UTC) > TOKEN_REFRESH_BUFFER:
            return account.access_token
        logger.info("Refreshing expired %s token for user %s", account.provider, account.user_id)
        credentials = ProviderCredentials(
            refresh_token=account.refresh_token,
            access_token=account.access_token,
            token_expires_at=account.token_expires_at,
            scope=account.scope,
        )
        fresh = adapter.refresh(credentials)
        # The refresh token rotates on Strava; store the latest pair.
        account.refresh_token = fresh.refresh_token
        account.access_token = fresh.access_token
        account.token_expires_at = fresh.token_expires_at
        account.scope = fresh.scope
        self._unit_of_work.commit()
        return fresh.access_token
