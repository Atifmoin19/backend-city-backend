"""Email verification and password reset (EmailJS off in tests: links land in the outbox)."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tokens import EmailToken
from app.services.mailer import outbox
from tests.conftest import register


@pytest.fixture(autouse=True)
def _empty_outbox() -> None:
    outbox.sent.clear()


def token_from(template: str, email: str) -> str:
    mail = next(
        m for m in reversed(outbox.sent) if m["template"] == template and m["to_email"] == email
    )
    return parse_qs(urlparse(mail["link"]).query)["token"][0]


async def test_signup_sends_a_verification_link_that_works_once(client: AsyncClient) -> None:
    user = await register(client)
    assert user["is_verified"] is False
    token = token_from("verify", "learner@example.com")
    assert outbox.sent[-1]["link"].startswith("http://localhost:3000/verify-email?token=")

    res = await client.post("/auth/verify-email", json={"token": token})
    assert res.status_code == 200 and res.json()["is_verified"] is True
    assert (await client.get("/auth/me")).json()["is_verified"] is True
    again = await client.post("/auth/verify-email", json={"token": token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_token"

    # already verified: resending sends nothing
    outbox.sent.clear()
    assert (await client.post("/auth/verify-email/resend")).status_code == 204
    assert outbox.sent == []


async def test_resend_replaces_the_old_link(client: AsyncClient) -> None:
    await register(client)
    first = token_from("verify", "learner@example.com")
    assert (await client.post("/auth/verify-email/resend")).status_code == 204
    second = token_from("verify", "learner@example.com")
    assert first != second
    assert (await client.post("/auth/verify-email", json={"token": first})).status_code == 400
    assert (await client.post("/auth/verify-email", json={"token": second})).status_code == 200


async def test_forgot_password_never_reveals_whether_an_email_exists(client: AsyncClient) -> None:
    res = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 204
    assert outbox.sent == []


async def test_reset_password_changes_it_and_signs_out_everywhere(client: AsyncClient) -> None:
    await register(client)
    old_refresh = client.cookies.get("bc_refresh")
    assert (
        await client.post("/auth/forgot-password", json={"email": " Learner@Example.com "})
    ).status_code == 204
    token = token_from("reset", "learner@example.com")

    short = await client.post("/auth/reset-password", json={"token": token, "password": "short"})
    assert short.status_code == 422
    ok = await client.post(
        "/auth/reset-password", json={"token": token, "password": "brand-new-pass-2"}
    )
    assert ok.status_code == 204
    reused = await client.post(
        "/auth/reset-password", json={"token": token, "password": "another-pass-3"}
    )
    assert reused.status_code == 400

    old = await client.post(
        "/auth/login", json={"email": "learner@example.com", "password": "learner-pass-1"}
    )
    assert old.status_code == 401
    new = await client.post(
        "/auth/login", json={"email": "learner@example.com", "password": "brand-new-pass-2"}
    )
    assert new.status_code == 200
    assert new.json()["user"]["is_verified"] is True  # the reset link proved the inbox
    if old_refresh:
        client.cookies.set("bc_refresh", old_refresh, path="/auth")
        assert (await client.post("/auth/refresh")).status_code == 401


async def test_expired_reset_link_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    await client.post("/auth/forgot-password", json={"email": "learner@example.com"})
    token = token_from("reset", "learner@example.com")
    await db.execute(update(EmailToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    await db.commit()
    res = await client.post(
        "/auth/reset-password", json={"token": token, "password": "new-pass-123"}
    )
    assert res.status_code == 400


async def test_a_verify_link_cannot_reset_a_password(client: AsyncClient) -> None:
    await register(client)
    token = token_from("verify", "learner@example.com")
    res = await client.post(
        "/auth/reset-password", json={"token": token, "password": "new-pass-123"}
    )
    assert res.status_code == 400
