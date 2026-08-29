"""At-rest encryption for stored secrets (provider client secrets).

Provider client secrets are encrypted with a per-deployment Fernet key
before they reach the database. The key is generated on first use and kept
in ``server_settings`` (row ``secret_key``), so no environment variable is
ever required. Encrypted values are urlsafe token strings (Fernet format).
"""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.dao.server_setting_dao import ServerSettingDao
from app.models.server_setting import ServerSetting

#: ``server_settings`` key holding the Fernet key for this deployment.
SECRET_KEY_SETTING = "secret_key"


class SecretsError(Exception):
    """A stored secret cannot be decrypted (wrong key or tampered token)."""


class SecretsBox:
    """Encrypts and decrypts secret values with one Fernet key."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new random Fernet key (32 urlsafe-base64 bytes)."""
        return Fernet.generate_key()

    def encrypt(self, plaintext: str) -> str:
        """Return the encrypted form of a secret (a urlsafe token string)."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Return the plaintext behind an encrypted token.

        Raises SecretsError when the token was not produced by this key or
        has been altered.
        """
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as error:
            raise SecretsError("Stored secret cannot be decrypted.") from error


def ensure_secrets_box(session: Session) -> SecretsBox:
    """The deployment's :class:`SecretsBox`, generating the key on first use.

    Reads the ``secret_key`` row from ``server_settings``; when absent it
    generates a new Fernet key, stores it, and commits. Called once at
    startup (single-threaded, so no locking is needed); the DB ``UNIQUE
    (key)`` constraint is the backstop. The resulting box is process-wide.
    """
    dao = ServerSettingDao(session)
    row = dao.get_by_key(SECRET_KEY_SETTING)
    if row is None:
        row = dao.add(
            ServerSetting(key=SECRET_KEY_SETTING, value=SecretsBox.generate_key().decode())
        )
        session.commit()
    return SecretsBox(row.value.encode())
