"""Application entry point for the health-tracker API."""

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.errors.handlers import register_error_handlers
from app.http.activities import router as activities_router
from app.http.auth import router as auth_router
from app.http.health import router as health_router
from app.http.providers import router as providers_router
from app.http.users import router as users_router
from app.logging_config import configure_logging
from app.providers import ProviderRegistry
from app.providers.strava import StravaAdapter
from app.security.rate_limiter import RateLimiter
from app.version import api_version


def _build_provider_registry(settings: Settings) -> ProviderRegistry:
    """One adapter per provider whose configuration is present.

    Providers without configuration (no credentials in the environment) are
    simply not registered: they read as "not available on this instance"
    (404) instead of erroring.
    """
    registry = ProviderRegistry()
    if settings.strava_client_id and settings.strava_client_secret:
        redirect_uri = settings.strava_redirect_uri or (
            f"{settings.public_base_url.rstrip('/')}/api/v1/providers/strava/oauth/callback"
        )
        registry.register(
            StravaAdapter(
                settings.strava_client_id,
                settings.strava_client_secret,
                redirect_uri=redirect_uri,
                scope=settings.strava_scope,
            )
        )
    return registry


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    application = FastAPI(title="health-tracker API", version=api_version())
    # Process-wide rate limiter shared by the auth routes (in-memory by design,
    # like the database engine: it must outlive a single request).
    application.state.rate_limiter = RateLimiter()
    # Process-wide provider registry (adapters hold their own HTTP connection
    # pools, so like the engine and limiter they outlive a single request).
    application.state.provider_registry = _build_provider_registry(get_settings())
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(activities_router)
    application.include_router(providers_router)
    return application


app = create_app()
