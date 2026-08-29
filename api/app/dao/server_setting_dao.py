"""Data access for server settings (deployment-level key/value rows)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base_dao import IntIdDao
from app.models.server_setting import ServerSetting


class ServerSettingDao(IntIdDao[ServerSetting]):
    """Reads and writes of the ``server_settings`` table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ServerSetting)

    def get_by_key(self, key: str) -> ServerSetting | None:
        """The active setting row for a key, or None."""
        statement = select(ServerSetting).where(
            ServerSetting.key == key,
            ServerSetting.deleted_at.is_(None),
        )
        return self.session.scalars(statement).unique().first()

    def add(self, setting: ServerSetting) -> ServerSetting:
        """Persist a new setting. The caller commits the session."""
        self.session.add(setting)
        self.session.flush()
        return setting

    def save(self, setting: ServerSetting) -> None:
        """Flush changes to an existing row. The caller commits the session."""
        self.session.flush()
