"""Data access for user accounts."""

from uuid import UUID

from sqlalchemy import select

from app.dao.base_dao import BaseDao
from app.models.user import User


class UserDao(BaseDao[User]):
    """Reads and writes of the ``users`` table.

    All lookups exclude soft-deleted accounts (``deleted_at IS NOT NULL``).
    """

    def add(self, user: User) -> User:
        """Persist a new user. The caller commits the session."""
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        """Fetch an active account by id, or None."""
        statement = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return self.session.scalars(statement).unique().first()

    def get_by_email(self, email: str) -> User | None:
        """Fetch an active account by normalized email, or None."""
        statement = select(User).where(User.email == email, User.deleted_at.is_(None))
        return self.session.scalars(statement).unique().first()
