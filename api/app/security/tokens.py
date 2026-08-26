"""JWT creation and verification (HS256).

Tokens are opaque to the client beyond the ``Authorization: Bearer <token>``
header. The only claim is ``sub`` (the user id) plus standard ``exp``/``iat``.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt


class TokenService:
    """Issue and verify signed JWTs for authenticated requests."""

    def __init__(self, secret: str, ttl_days: int) -> None:
        self._secret = secret
        self._ttl = timedelta(days=ttl_days)

    def issue(self, user_id: UUID) -> str:
        """Create a signed token for the given user id."""
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify(self, token: str) -> UUID | None:
        """Return the user id encoded in a valid token, else None.

        Expired, tampered, or malformed tokens all yield None.
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        subject = payload.get("sub")
        if not isinstance(subject, str):
            return None
        try:
            return UUID(subject)
        except ValueError:
            return None
