"""DAO for the providers reference table (global, not user-scoped)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import BaseDao
from app.models.provider import Provider


class ProviderDao(BaseDao[Provider]):
    """Read access to the seeded provider reference rows."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Provider)

    def list_all(self) -> list[Provider]:
        """Every known provider, in value order."""
        statement = select(Provider).order_by(Provider.value)
        return list(self.session.scalars(statement))
