"""Application entry point for the health-tracker API."""

from fastapi import FastAPI

from app.config import get_settings
from app.db.session import make_session_factory
from app.errors.handlers import register_error_handlers
from app.http.activities import router as activities_router
from app.http.auth import router as auth_router
from app.http.health import router as health_router
from app.http.providers import router as providers_router
from app.http.users import router as users_router
from app.logging_config import configure_logging
from app.providers.factory import build_provider_registry
from app.security.rate_limiter import RateLimiter
from app.security.secrets import ensure_secrets_box
from app.version import api_version


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    application = FastAPI(title="health-tracker API", version=api_version())
    # Process-wide rate limiter shared by the auth routes (in-memory by design,
    # like the database engine: it must outlive a single request).
    application.state.rate_limiter = RateLimiter()
    # Process-wide secrets box + provider registry: the deployment's Fernet
    # key is generated on first use and stored in server_settings, and one
    # adapter is registered per provider with a stored, usable credential
    # set (the database is the only source of credentials). Like the engine
    # and limiter they outlive a single request; startup is single-threaded,
    # so the get-or-generate needs no locking.
    with make_session_factory()() as startup_session:
        application.state.secrets_box = ensure_secrets_box(startup_session)
        application.state.provider_registry = build_provider_registry(
            get_settings(), startup_session, application.state.secrets_box
        )
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(activities_router)
    application.include_router(providers_router)
    return application


app = create_app()
