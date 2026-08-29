"""Data access for provider credentials (deployment-level OAuth clients)."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.provider_credential import ProviderCredential


class ProviderCredentialDao(IntIdDao[ProviderCredential]):
    """Reads and writes of the ``provider_credentials`` table.

    Server-level rows (one per provider), so there is no user scoping.
    Lookups exclude soft-deleted rows unless noted. The ``client_secret``
    column holds the encrypted form; this DAO never touches plaintext.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, ProviderCredential)

    def get_active(self, provider: str) -> ProviderCredential | None:
        """The active credential set for a provider, or None."""
        statement = select(ProviderCredential).where(
            ProviderCredential.provider == provider,
            ProviderCredential.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def get_any(self, provider: str) -> ProviderCredential | None:
        """The credential row for a provider, including soft-deleted.

        ``UNIQUE (provider)`` spans all rows, so a reconfiguration must
        reuse the existing (possibly deleted) row instead of inserting a
        new one.
        """
        statement = select(ProviderCredential).where(ProviderCredential.provider == provider)
        return self.session.scalars(statement).unique().first()

    def add(self, credential: ProviderCredential) -> ProviderCredential:
        """Persist a new credential set. The caller commits the session."""
        self.session.add(credential)
        self.session.flush()
        return credential

    def save(self, credential: ProviderCredential) -> None:
        """Flush changes to an existing row. The caller commits the session."""
        self.session.flush()

    def mark_deleted(self, provider: str) -> None:
        """Soft-delete the credential set for a provider (no-op when absent)."""
        statement = (
            update(ProviderCredential)
            .where(
                ProviderCredential.provider == provider,
                ProviderCredential.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        self.session.execute(statement)
