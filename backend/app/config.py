"""Application settings, read from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Local development uses SQLite. Production uses the Neon Postgres URL.
    database_url: str = "sqlite:///./koshio.db"

    # Must be a long random string in production (the app refuses to start without one).
    jwt_secret: str = ""
    jwt_expire_minutes: int = 12 * 60

    # Koshio is a personal app: once the first account exists, sign-up closes
    # unless ALLOW_MULTIPLE_USERS is true.
    allow_registration: bool = True
    allow_multiple_users: bool = False

    # Comma-separated list of web addresses allowed to call the API,
    # e.g. https://vinusmiles.github.io
    cors_origins: str = "http://localhost:5173"

    environment: str = "development"  # "development" | "production" | "test"

    # Optional: lets Koshio ask Claude to suggest categories from merchant names.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Neon and Render hand out postgres:// or postgresql:// URLs; use the psycopg 3 driver.
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
