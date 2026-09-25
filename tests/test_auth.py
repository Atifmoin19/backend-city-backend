from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.models.enums import Role
from app.models.user import User

CREDS = {"email": "Ana@Example.com", "password": "correct-horse-1", "display_name": "Ana"}


async def register(client: AsyncClient) -> dict[str, object]:
    res = await client.post("/auth/register", json=CREDS)
    assert res.status_code == 201, res.text
    return dict(res.json()["user"])


async def test_register_sets_httponly_cookies_and_hides_secrets(client: AsyncClient) -> None:
    res = await client.post("/auth/register", json=CREDS)
    assert res.status_code == 201
    user = res.json()["user"]
    assert user["email"] == "ana@example.com"  # normalized
    assert user["role"] == "user"
    assert "password_hash" not in user
    set_cookie = res.headers.get_list("set-cookie")
    assert any(c.startswith(f"{ACCESS_COOKIE}=") and "HttpOnly" in c for c in set_cookie)
    assert any(c.startswith(f"{REFRESH_COOKIE}=") and "Path=/auth" in c for c in set_cookie)


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await register(client)
    res = await client.post("/auth/register", json=CREDS)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


async def test_register_validation_uses_error_envelope(client: AsyncClient) -> None:
    res = await client.post("/auth/register", json={**CREDS, "password": "short"})
    assert res.status_code == 422
    body = res.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["body", "password"]


async def test_login_rejects_bad_password_and_unknown_email_identically(
    client: AsyncClient,
) -> None:
    await register(client)
    client.cookies.clear()
    wrong = await client.post("/auth/login", json={"email": CREDS["email"], "password": "nope"})
    unknown = await client.post("/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_login_then_me(client: AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    assert (await client.get("/auth/me")).status_code == 401
    res = await client.post(
        "/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    assert res.status_code == 200
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "Ana"


async def test_refresh_rotates_and_detects_reuse(client: AsyncClient) -> None:
    await register(client)
    first = client.cookies[REFRESH_COOKIE]

    rotated = await client.post("/auth/refresh")
    assert rotated.status_code == 200
    second = client.cookies[REFRESH_COOKIE]
    assert second != first

    # Replay the old (already rotated) token -> reuse detected, all sessions revoked
    client.cookies.clear()
    replay = await client.post("/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={first}"})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_reused"

    client.cookies.clear()
    after = await client.post("/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={second}"})
    assert after.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await register(client)
    token = client.cookies[REFRESH_COOKIE]
    assert (await client.post("/auth/logout")).status_code == 204
    client.cookies.clear()
    res = await client.post("/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={token}"})
    assert res.status_code == 401


async def test_blocked_user_cannot_login(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    await db.execute(update(User).values(is_blocked=True))
    await db.commit()
    client.cookies.clear()
    res = await client.post(
        "/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "account_blocked"


async def test_admin_route_requires_role(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    denied = await client.get("/admin/whoami")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden_role"

    await db.execute(update(User).values(role=Role.CONTENT_EDITOR))
    await db.commit()
    allowed = await client.get("/admin/whoami")
    assert allowed.status_code == 200
    assert allowed.json()["role"] == "content_editor"


async def test_admin_route_rejects_anonymous(client: AsyncClient) -> None:
    res = await client.get("/admin/whoami")
    assert res.status_code == 401
