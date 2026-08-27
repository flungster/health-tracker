"""JWT creation and verification (HS256).

Tokens are opaque to the client beyond the ``Authorization: Bearer <token>``
header. The only claim is ``sub`` (the user id) plus standard ``exp``/``iat``.

OAuth state tokens are a second, short-lived token kind: they bind a provider
OAuth flow to the user who started it, so the callback (a plain browser
redirect that carries no ``Authorization`` header) can identify the user.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

#: ``purpose`` claim marking a token as an OAuth state token.
OAUTH_STATE_PURPOSE = "oauth_state"
#: OAuth flows complete in seconds to minutes, not days.
OAUTH_STATE_TTL = timedelta(minutes=10)


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

    def issue_oauth_state(self, user_id: UUID) -> str:
        """A short-lived signed token binding an OAuth flow to a user.

        Placed in the provider authorize URL as ``state``; verified verbatim
        on the callback to (a) reject forged/crossed flows (CSRF) and (b)
        identify the user, whose browser does not send our JWT on the
        provider's redirect.
        """
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "purpose": OAUTH_STATE_PURPOSE,
            "iat": now,
            "exp": now + OAUTH_STATE_TTL,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify_oauth_state(self, token: str) -> UUID | None:
        """The user an OAuth state token binds to, else None.

        Expired, tampered, malformed tokens — and tokens of any other kind
        (e.g. a session JWT) — all yield None.
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        if payload.get("purpose") != OAUTH_STATE_PURPOSE:
            return None
        subject = payload.get("sub")
        if not isinstance(subject, str):
            return None
        try:
            return UUID(subject)
        except ValueError:
            return None
