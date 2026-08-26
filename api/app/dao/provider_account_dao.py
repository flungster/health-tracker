"""Data access for provider accounts (a user's connected third-party profiles)."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.provider_account import ProviderAccount


class ProviderAccountDao(IntIdDao[ProviderAccount]):
    """Reads and writes of the ``provider_accounts`` table.

    All lookups exclude soft-deleted rows (``deleted_at IS NOT NULL``) and
    are scoped to the owning user.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, ProviderAccount)

    def add(self, account: ProviderAccount) -> ProviderAccount:
        """Persist a new connection. The caller commits the session."""
        self.session.add(account)
        self.session.flush()
        return account

    def get_for_user(self, user_uuid: UUID, provider: str) -> ProviderAccount | None:
        """The user's active connection for a provider, or None."""
        statement = select(ProviderAccount).where(
            ProviderAccount.user_id == user_uuid,
            ProviderAccount.provider == provider,
            ProviderAccount.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def mark_deleted(self, user_uuid: UUID, provider: str) -> None:
        """Soft-delete the user's connection for a provider (no-op when absent)."""
        statement = (
            update(ProviderAccount)
            .where(
                ProviderAccount.user_id == user_uuid,
                ProviderAccount.provider == provider,
                ProviderAccount.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        self.session.execute(statement)
