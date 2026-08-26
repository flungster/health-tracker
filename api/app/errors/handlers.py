"""Global exception handlers producing the structured error envelope.

Every error response has the shape:

    {"error": {"code": "...", "message": "...", "details": [...]}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors.app_error import AppError, RateLimitExceededError

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: list[str]) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach the error envelope handlers to the application."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        headers: dict[str, str] | None = None
        if isinstance(exc, RateLimitExceededError):
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []))
            details.append(f"{location}: {error.get('msg', 'invalid value')}")
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", "The request body is invalid.", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the full error server-side; never leak internals to clients.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred.", []),
        )
