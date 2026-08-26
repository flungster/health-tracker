"""Application entry point for the health-tracker API."""

from fastapi import FastAPI

from app.errors.handlers import register_error_handlers
from app.http.activities import router as activities_router
from app.http.auth import router as auth_router
from app.http.health import router as health_router
from app.http.users import router as users_router
from app.logging_config import configure_logging
from app.security.rate_limiter import RateLimiter
from app.version import api_version


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    application = FastAPI(title="health-tracker API", version=api_version())
    # Process-wide rate limiter shared by the auth routes (in-memory by design,
    # like the database engine: it must outlive a single request).
    application.state.rate_limiter = RateLimiter()
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(activities_router)
    return application


app = create_app()
