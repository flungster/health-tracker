"""Unit of work: the explicit transaction boundary for one unit of work.

A single request is one unit of work: all of its DAO reads and writes happen
against one session, and the unit of work decides when those writes become
durable. This mirrors the classic "unit of work" pattern from the ORM/Java
world — the session is the work in progress, and :meth:`commit` makes it
permanent.

DAOs never commit; they only stage changes on the session. The owning service
calls :meth:`commit` when a business operation succeeds, which keeps multi-DAO
operations (such as an import that writes the activity, its trackpoints, splits,
and sport row) atomic: either all of it lands or none of it does.
"""

from sqlalchemy.orm import Session


class UnitOfWork:
    """Owns the session for a single unit of work (typically one request)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        """The underlying SQLAlchemy session, shared by all DAOs in this unit."""
        return self._session

    def commit(self) -> None:
        """Make every staged write in this unit of work durable."""
        self._session.commit()

    def rollback(self) -> None:
        """Discard every staged write in this unit of work."""
        self._session.rollback()

    def close(self) -> None:
        """Release the session back to the connection pool."""
        self._session.close()
