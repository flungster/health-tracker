"""Provider credential model: the deployment's own OAuth client for one provider."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class ProviderCredential(IntIdModel, TimestampMixin):
    """The deployment's own OAuth client credentials for one provider.

    Configured via the UI (M11) instead of environment variables. The
    ``client_secret`` column holds the encrypted form (Fernet); plaintext
    secrets are never persisted or exposed through the API. Per-user
    connections (the user's own tokens) live in ``provider_accounts``.
    """

    __tablename__ = "provider_credentials"

    # FK to providers.value lives in the migration SQL (reference tables
    # have no ORM model), mirroring ProviderAccount.provider.
    provider: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"ProviderCredential(provider={self.provider!r})"
