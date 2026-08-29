"""Server setting model: deployment-level key/value settings (not per-user)."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IntIdModel, TimestampMixin


class ServerSetting(IntIdModel, TimestampMixin):
    """A deployment-level key/value setting.

    First tenant: the ``secret_key`` row holding the Fernet key used to
    encrypt provider client secrets at rest (see ``app.security.secrets``).
    """

    __tablename__ = "server_settings"

    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"ServerSetting(key={self.key!r})"
