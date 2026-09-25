from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.rate_limit import limiter


@pytest.fixture
def rate_limit_on() -> Iterator[None]:
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


@pytest.mark.usefixtures("rate_limit_on")
async def test_login_is_rate_limited(client: AsyncClient) -> None:
    body = {"email": "a@example.com", "password": "x"}
    statuses = [(await client.post("/auth/login", json=body)).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    last = await client.post("/auth/login", json=body)
    assert last.json()["error"]["code"] == "rate_limited"


@pytest.fixture
def proxy_secret() -> Iterator[str]:
    settings = get_settings()
    settings.proxy_shared_secret = SecretStr("proxy-secret-for-tests")
    yield "proxy-secret-for-tests"
    settings.proxy_shared_secret = None


@pytest.mark.usefixtures("rate_limit_on")
async def test_limits_key_on_the_real_client_ip_behind_the_proxy(
    client: AsyncClient, proxy_secret: str
) -> None:
    """Behind Vercel every request comes from Vercel; the signed header separates learners."""
    body = {"email": "a@example.com", "password": "x"}

    def via_proxy(ip: str) -> dict[str, str]:
        return {"x-bc-client-ip": ip, "x-bc-proxy-secret": proxy_secret}

    for _ in range(10):
        await client.post("/auth/login", json=body, headers=via_proxy("1.1.1.1"))
    blocked = await client.post("/auth/login", json=body, headers=via_proxy("1.1.1.1"))
    other = await client.post("/auth/login", json=body, headers=via_proxy("2.2.2.2"))
    assert blocked.status_code == 429
    assert other.status_code == 401


@pytest.mark.usefixtures("rate_limit_on")
async def test_forged_client_ip_without_the_secret_is_ignored(
    client: AsyncClient, proxy_secret: str
) -> None:
    body = {"email": "a@example.com", "password": "x"}
    statuses = []
    for i in range(11):
        forged = {"x-bc-client-ip": f"9.9.9.{i}", "x-bc-proxy-secret": "wrong"}
        statuses.append((await client.post("/auth/login", json=body, headers=forged)).status_code)
    assert statuses[10] == 429  # all counted against the real peer
