"""Typed application settings loaded from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Full Stack City API"
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

    @field_validator("database_url", mode="before")
    @classmethod
    def _asyncpg_url(cls, v: object) -> object:
        """Accept a connection string pasted from Neon/Render as-is.

        asyncpg needs the `postgresql+asyncpg` scheme and `ssl=` (it rejects libpq's `sslmode`
        and `channel_binding`), so translate those here instead of asking humans to.
        """
        if not isinstance(v, str):
            return v
        parts = urlsplit(v)
        scheme = parts.scheme
        if scheme in ("postgres", "postgresql"):
            scheme = "postgresql+asyncpg"
        query = []
        for key, value in parse_qsl(parts.query):
            if key == "channel_binding":
                continue
            if key == "sslmode":
                key, value = (
                    "ssl",
                    "require" if value in ("require", "verify-ca", "verify-full") else value,
                )
            query.append((key, value))
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

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
    feedback_rate_limit: str = "10/hour"
    # Shared with the frontend proxy (PROXY_SHARED_SECRET on Vercel). When a request carries
    # it, its X-BC-Client-IP header is the learner's real IP; every request otherwise looks
    # like it came from Vercel, so all learners would share one rate-limit bucket.
    proxy_shared_secret: SecretStr | None = None

    # CORS — only needed for direct calls; production uses same-origin rewrites
    cors_origins: list[str] = ["http://localhost:3000"]

    # Scoring: each hint tier used lowers the checkpoint's maximum score by this many points
    hint_penalty_per_tier: int = 5

    # Sandbox
    sandbox_timeout_seconds: float = 4.0  # learner code only
    sandbox_startup_seconds: float = 20.0  # interpreter + imports allowance (slow CPUs)
    sandbox_memory_limit_mb: int = 256
    sandbox_max_snippet_chars: int = 4000
    # Keep a pre-imported fork server running so a grade doesn't pay interpreter start +
    # FastAPI imports (7-11 s on Render's 0.1 CPU). Falls back to cold runs if it can't start.
    sandbox_warm: bool = True
    # grades the warm fork server runs at once (each is a forked child: little extra memory)
    sandbox_parallel: int = 2
    # Interpreter for the grading sandbox (venv built from harness/requirements.txt).
    # Empty = current interpreter (fine for local dev/tests).
    sandbox_python: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
