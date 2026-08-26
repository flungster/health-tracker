"""User account model."""

from uuid import UUID

from sqlalchemy import Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """An application account.

    ``email`` is always stored normalized (trimmed, lower-case); uniqueness is
    therefore case-insensitive by construction.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"
