"""Expected application errors.

Services and DAOs raise these when something goes wrong in a predictable way
(wrong password, duplicate email, missing activity...). The global exception
handlers in ``app.errors.handlers`` translate them into the structured JSON
error envelope returned to clients.
"""


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details if details is not None else []


class AuthenticationError(AppError):
    """Missing, invalid, or expired credentials (HTTP 401)."""

    status_code = 401
    code = "UNAUTHENTICATED"


class NotFoundError(AppError):
    """The requested resource does not exist for this user (HTTP 404)."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """The request conflicts with current state, e.g. duplicate email (409)."""

    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    """Business-level input validation failed (HTTP 422)."""

    status_code = 422
    code = "VALIDATION_ERROR"


class RateLimitExceededError(AppError):
    """A client exceeded its per-minute request allowance (HTTP 429).

    Carries ``retry_after_seconds`` so the response can include a
    ``Retry-After`` header.
    """

    status_code = 429
    code = "RATE_LIMITED"

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderUpstreamError(AppError):
    """A provider's API failed or rejected the request (HTTP 502).

    Raised by provider adapters for network failures, provider-side errors,
    and invalid or revoked credentials.
    """

    status_code = 502
    code = "PROVIDER_ERROR"


class ActivityImportError(AppError):
    """An uploaded activity file could not be read (HTTP 422).

    Raised by the format parsers and the import service when the file is
    not a valid GPX/TCX/FIT activity file (corrupt data, wrong format, no
    trackpoints, ...).
    """

    status_code = 422
    code = "IMPORT_ERROR"
