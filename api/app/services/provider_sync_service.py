"""Provider sync: pull a connected user's activities from their provider.

A sync run walks the provider's activity list from the stored cursor (the
walk goes newest -> older, one page per adapter call) and imports every
activity not imported before — deduped by the global
``(provider, external_activity_id)`` index, so re-syncing only pulls what is
new. The cursor is checkpointed after each full page, so an interrupted or
rate-limited run resumes where it stopped; a run that finishes the walk
clears the cursor.

Provider failures surface as ``ProviderUpstreamError`` (502); a rate limit
carries ``retry_after_seconds`` (the response gets a ``Retry-After`` header).
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.dao.activity_dao import ActivityDao
from app.dao.provider_account_dao import ProviderAccountDao
from app.db.unit_of_work import UnitOfWork
from app.errors.app_error import NotFoundError
from app.models.provider_account import ProviderAccount
from app.providers.base import ProviderAdapter, ProviderCredentials
from app.providers.registry import ProviderRegistry
from app.schemas.views.provider_views import SyncResultView
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

    def sync(self, user_uuid: UUID, provider: str) -> SyncResultView:
        """Run one sync. Commits per imported activity and per cursor page.

        Raises NotFoundError when there is no active connection (or the
        provider is unknown/unconfigured) and ProviderUpstreamError when the
        provider fails (with ``retry_after_seconds`` on a rate limit).
        """
        account = self._account_dao.get_for_user(user_uuid, provider)
        if account is None:
            raise NotFoundError(f"No {provider} connection to sync.")
        adapter = self._registry.get(provider)
        access_token = self._ensure_access_token(adapter, account)

        cursor = account.sync_cursor
        imported = 0
        skipped = 0
        walk_complete = False
        pages = 0
        while True:
            pages += 1
            page = adapter.fetch_activity_ids(access_token, cursor)
            for external_id in page.external_activity_ids:
                if self._activity_dao.exists_for_provider(provider, external_id):
                    skipped += 1
                    continue
                parsed = adapter.fetch_activity(access_token, external_id)
                self._import_service.import_parsed(
                    user_uuid,
                    parsed,
                    provider=provider,
                    external_activity_id=external_id,
                )
                imported += 1
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
            "%s sync for user %s: %d imported, %d skipped (%d pages)",
            provider,
            user_uuid,
            imported,
            skipped,
            pages,
        )
        return SyncResultView(imported=imported, skipped=skipped, last_sync_at=account.last_sync_at)

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
