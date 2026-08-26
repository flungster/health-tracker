"""Runtime configuration for the API service.

Settings are read from environment variables. During local development a
`.env` file in the current working directory is also consulted.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration.

    Attribute names map to upper-case environment variables, e.g.
    ``database_url`` -> ``DATABASE_URL``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://healthtracker:healthtracker@localhost:5432/health_tracker"
    )
    # Development default only; production must set JWT_SECRET to a long
    # random value (e.g. `openssl rand -hex 32`).
    jwt_secret: str = "insecure-dev-secret-000000000000000000000000000000"
    jwt_token_ttl_days: int = 30
    uploads_dir: str = "/data/uploads"
    max_upload_mb: int = 50
    # Maximum trackpoints in one imported file; larger files are rejected so
    # a single upload cannot exhaust memory (or the trackpoints endpoint).
    max_trackpoints: int = 100_000
    # Per-minute auth limits per client IP (brute-force / spam protection).
    login_rate_limit_per_minute: int = 10
    register_rate_limit_per_minute: int = 5


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency returning the process-wide settings instance.

    Components that need configuration receive it through constructor
    injection (wired via ``Depends(get_settings)``) rather than calling this
    themselves, so dependencies stay explicit and tests can override it.
    """
    return Settings()
