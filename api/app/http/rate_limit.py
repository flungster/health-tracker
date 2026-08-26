"""Rate-limit dependencies for the authentication endpoints.

Login and register are throttled per client IP so a single address cannot
brute-force passwords or spam account creation. The limits come from the
injected settings; the limiter itself is the process-wide instance wired
onto ``app.state`` by ``create_app``.
"""

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors.app_error import RateLimitExceededError
from app.security.rate_limiter import RateLimiter

# Both limits are expressed per minute, so both use a one-minute window.
_WINDOW_SECONDS = 60


def _limiter(request: Request) -> RateLimiter:
    # ``app.state`` is Starlette's untyped attribute bag (Any), so bind it
    # to the concrete type here.
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


def _client_ip(request: Request) -> str:
    if request.client is not None:
        return request.client.host
    return "unknown"


def limit_login(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Allow a login attempt, or raise a 429 if this IP is over its limit."""
    retry_after = _limiter(request).check(
        f"login:{_client_ip(request)}", settings.login_rate_limit_per_minute, _WINDOW_SECONDS
    )
    if retry_after is not None:
        raise RateLimitExceededError("Too many login attempts; try again shortly.", retry_after)


def limit_register(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Allow a registration, or raise a 429 if this IP is over its limit."""
    retry_after = _limiter(request).check(
        f"register:{_client_ip(request)}",
        settings.register_rate_limit_per_minute,
        _WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise RateLimitExceededError("Too many registrations; try again shortly.", retry_after)
