"""Shared base for all data access objects."""

from sqlalchemy.orm import Session


class BaseDao[ModelT]:
    """Holds the request-scoped session for concrete DAOs.

    Concrete DAOs add their own query methods; they must never create or
    commit sessions here — commits are the service layer's responsibility.
    ``ModelT`` names the ORM model the DAO operates on.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        """The session this DAO operates on."""
        return self._session
