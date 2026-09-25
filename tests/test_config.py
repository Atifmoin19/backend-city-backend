from app.core.config import Settings


def test_neon_connection_string_is_translated_for_asyncpg() -> None:
    raw = "postgresql://u:p@ep-x.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    url = str(Settings(database_url=raw).database_url)  # type: ignore[arg-type]
    assert url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in url
    assert "sslmode" not in url
    assert "channel_binding" not in url


def test_local_asyncpg_url_is_unchanged() -> None:
    raw = "postgresql+asyncpg://backend_city:backend_city@localhost:5452/backend_city"
    assert str(Settings(database_url=raw).database_url) == raw  # type: ignore[arg-type]
