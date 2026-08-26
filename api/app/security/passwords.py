"""Password hashing using argon2id.

The plaintext password is never stored or logged. Only the argon2id hash is
persisted in ``users.password_hash``.
"""

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerificationError


class PasswordService:
    """Hash and verify passwords with argon2id (argon2-cffi defaults)."""

    def __init__(self) -> None:
        # PasswordHasher uses the OWASP-recommended argon2id parameters.
        self._hasher = PasswordHasher()

    def hash(self, plaintext: str) -> str:
        """Return the argon2id hash for a plaintext password."""
        return self._hasher.hash(plaintext)

    def verify(self, plaintext: str, password_hash: str) -> bool:
        """Return True when the plaintext matches the stored hash.

        All verification failures (wrong password, malformed hash) return
        False so callers can treat them uniformly.
        """
        try:
            return self._hasher.verify(password_hash, plaintext)
        except (VerificationError, InvalidHashError, Argon2Error):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Return True when a hash should be regenerated with new parameters."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except (InvalidHashError, Argon2Error):
            return True
