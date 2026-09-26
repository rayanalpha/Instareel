"""Central application settings (pydantic-settings, loaded from .env)."""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"
DEFAULT_SYNC_DATABASE_URL = "sqlite:///./data/app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "IG Funnel"
    ENV: str = "production"
    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = ""
    APP_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    # Sync URL for Celery workers (sync SQLAlchemy engine — never asyncio in tasks).
    SYNC_DATABASE_URL: str = DEFAULT_SYNC_DATABASE_URL
    REDIS_URL: str = "redis://localhost:6379/0"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme-please"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 7
    # Self-docs (/docs, /redoc, /openapi.json) are OFF by default — they
    # enumerate every route. Enable only on trusted networks / local dev.
    DOCS_ENABLED: bool = False

    # IANA timezone whose wall-clock the schedule-rule hours follow.
    # A rule set for "12:00" fires at 12:00 in THIS zone — set it to your own
    # (e.g. Asia/Tehran) so the dashboard times match reality. Beat crontabs
    # (daily reset, cleanup, …) follow it too.
    SCHEDULE_TZ: str = "UTC"

    MEDIA_ROOT: str = "./media"
    MAX_UPLOAD_MB: int = 500
    AUTO_PROCESS_ON_UPLOAD: bool = True

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    IG_DEFAULT_MAX_DAILY_POSTS: int = 3
    IG_PRE_POST_DELAY_MIN: int = 30
    IG_PRE_POST_DELAY_MAX: int = 120

    @model_validator(mode="after")
    def _derive_sync_url(self):
        """If only the async URL was customized, derive the sync one from it."""
        if self.SYNC_DATABASE_URL == DEFAULT_SYNC_DATABASE_URL and self.DATABASE_URL != DEFAULT_DATABASE_URL:
            if "+aiosqlite" in self.DATABASE_URL:
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace("+aiosqlite", "")
            elif "+asyncpg" in self.DATABASE_URL:
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        return self

    @model_validator(mode="after")
    def _validate_schedule_tz(self):
        """SCHEDULE_TZ must be a real IANA zone — a typo must not silently
        shift every post by hours. Fall back to UTC with a loud warning."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.SCHEDULE_TZ)
        except (ZoneInfoNotFoundError, ValueError):
            import logging

            logging.getLogger("igfunnel").warning(
                "Invalid SCHEDULE_TZ=%r — falling back to UTC", self.SCHEDULE_TZ
            )
            self.SCHEDULE_TZ = "UTC"
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.FERNET_KEY:
        from cryptography.fernet import Fernet

        settings.FERNET_KEY = Fernet.generate_key().decode()
        import logging

        logging.getLogger(__name__).warning(
            "FERNET_KEY not set — generated an ephemeral key. "
            "Encrypted credentials will be unreadable after restart. "
            "Set FERNET_KEY in .env (see .env.example)."
        )
    return settings


settings = get_settings()
