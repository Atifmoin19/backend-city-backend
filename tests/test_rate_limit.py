from collections.abc import Iterator

import pytest
from httpx import AsyncClient

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
