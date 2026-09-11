"""The HttpOnly session cookie mirroring the Bearer JWT.

Every JSON API call authenticates with ``Authorization: Bearer <token>``
(the SPA keeps the token in localStorage). Browser subresources — activity
photo ``<img>`` tags (M22) foremost among them — cannot set request headers,
so login and register additionally place the same JWT in an HttpOnly cookie
scoped to the API prefix, and request authentication accepts it as a fallback.

See ``docs/adr/m22a-cookie-session-auth.md`` for the security analysis
(SameSite=Lax, why Bearer stays primary).
"""

from starlette.responses import Response

#: Cookie name carrying the session JWT.
COOKIE_NAME = "ht_session"
#: The cookie is only sent for API routes, never app pages.
COOKIE_PATH = "/api/v1"


def set_session_cookie(
    response: Response, token: str, max_age_seconds: int, secure: bool = False
) -> None:
    """Attach the session JWT as an HttpOnly, SameSite=Lax cookie."""
    response.set_cookie(
        COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie (logout)."""
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
