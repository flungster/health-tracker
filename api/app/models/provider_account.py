"""Provider account model: one of a local user's connected third-party profiles."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class ProviderAccount(IntIdModel, TimestampMixin):
    """A local user's own profile on one external provider (e.g. Strava).

    Carries the external identity, the OAuth credentials used to fetch the
    user's own activities, and the sync state. Never another person's
    profile, and never exposed through the API (tokens included).
    """

    __tablename__ = "provider_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="provider_accounts_user_id_provider_key"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False
    )
    # FK to providers.value lives in the migration SQL (reference tables
    # have no ORM model), mirroring Activity.sport_type/source_format.
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"ProviderAccount(user_id={self.user_id}, provider={self.provider!r})"
