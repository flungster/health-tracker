"""Shared bases for all data access objects.

``BaseDao`` holds the request-scoped session and the ORM model (injected so
the shared methods can query it without each DAO repeating itself).
``IntIdDao``/``IntIdUuidDao`` add the fetch-by-key methods that follow from
the identifier convention (see ``app.models.base``).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import IntIdModel, IntIdUuidModel


class BaseDao[ModelT]:
    """Holds the request-scoped session for concrete DAOs.

    Concrete DAOs add their own query methods; they must never create or
    commit sessions here — commits are the service layer's responsibility.
    ``ModelT`` names the ORM model the DAO operates on.
    """

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    @property
    def session(self) -> Session:
        """The session this DAO operates on."""
        return self._session

    @property
    def model(self) -> type[ModelT]:
        """The ORM model this DAO operates on."""
        return self._model

    def list(self, offset: int = 0, limit: int = 50) -> list[ModelT]:
        """A basic page of rows (offset/limit pagination), unscoped.

        Concrete DAOs add scoped/ordered variants on top; user-owned data
        must be filtered by ``user_id`` in those variants. This method is
        the shared primitive (and the query path for reference tables).
        """
        statement = select(self._model).offset(offset).limit(limit)
        return list(self.session.scalars(statement))


class IntIdDao[ModelT: IntIdModel](BaseDao[ModelT]):
    """Base for DAOs of tables with an int ``id`` primary key."""

    def get_by_id(self, id: int) -> ModelT | None:
        """Fetch a row by its internal int id (primary key)."""
        return self.session.get(self._model, id)


class IntIdUuidDao[ModelT: IntIdUuidModel](IntIdDao[ModelT]):
    """Base for DAOs of int-PK tables that also expose a public ``uuid``.

    Extends ``IntIdDao`` so both fetchers are available: the internal
    ``get_by_id`` and the public ``get_by_uuid``.
    """

    def get_by_uuid(self, uuid: UUID) -> ModelT | None:
        """Fetch a row by its public uuid (the identifier used in URLs/API)."""
        statement = select(self._model).where(self._model.uuid == uuid)
        return self.session.scalars(statement).first()
