"""ORM model for the ui_themes reference table."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UiTheme(Base):
    """A UI theme a user can select.

    Reference table: primary key is the value itself (the public API
    string), rows are seeded by migration and never updated or deleted, so
    there are no ``updated_at``/``deleted_at`` audit columns here. The app
    default (when a profile stores NULL) is ``light``; ``system`` follows the
    OS color scheme and is resolved client-side.
    """

    __tablename__ = "ui_themes"

    value: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"UiTheme(value={self.value!r})"
