"""Test setup. Env vars are set BEFORE importing the app so cached settings pick them up.

Tests run against the `backend_city_test` database from docker-compose (host port 5452):
    docker compose up -d db
"""

import os

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://backend_city:backend_city@localhost:5452/backend_city_test",
        ),
        "JWT_SECRET": "test-secret-with-enough-length-for-hs256-0123456789",
        "COOKIE_SECURE": "false",
        "REFRESH_COOKIE_PATH": "/auth",  # tests call the backend directly, no /api rewrite
        "RATE_LIMIT_ENABLED": "false",
    }
)

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionFactory, engine
from app.games.seed import sync
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    """Every test starts with the seed content and no users; everything is wiped after."""
    async with SessionFactory() as session:
        await sync(session)
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register(client: AsyncClient, email: str = "learner@example.com") -> dict[str, object]:
    res = await client.post(
        "/auth/register",
        json={"email": email, "password": "learner-pass-1", "display_name": "Learner"},
    )
    assert res.status_code == 201, res.text
    user: dict[str, object] = res.json()["user"]
    return user
