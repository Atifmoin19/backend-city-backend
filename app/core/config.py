"""Typed application settings loaded from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Backend City API"
    environment: Literal["local", "test", "production"] = "local"
    debug: bool = False
    api_prefix: str = ""

    # Database (asyncpg driver URL)
    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+asyncpg://backend_city:backend_city@localhost:5452/backend_city"
        )
    )
    db_echo: bool = False

    # Auth
    jwt_secret: SecretStr = SecretStr("change-me-in-env")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    cookie_secure: bool = True
    cookie_domain: str | None = None
    # Browser-visible path: frontend rewrites /api/* -> backend, so refresh is under /api/auth
    refresh_cookie_path: str = "/api/auth"

    # Rate limits (slowapi syntax)
    rate_limit_enabled: bool = True
    auth_rate_limit: str = "10/minute"
    checkpoint_rate_limit: str = "20/minute"

    # CORS — only needed for direct calls; production uses same-origin rewrites
    cors_origins: list[str] = ["http://localhost:3000"]

    # Sandbox
    sandbox_timeout_seconds: float = 4.0
    sandbox_memory_limit_mb: int = 256
    sandbox_max_snippet_chars: int = 4000
    # Interpreter for the grading sandbox (venv built from harness/requirements.txt).
    # Empty = current interpreter (fine for local dev/tests).
    sandbox_python: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
