from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.games import catalog
from app.games.seed import sync
from app.games.variants import pick_params, render
from app.models.enums import Role
from app.models.user import User
from tests.conftest import register

GATE = "ticket-booth"


async def as_role(client: AsyncClient, db: AsyncSession, role: Role, email: str) -> dict[str, Any]:
    user = await register(client, email)
    await db.execute(update(User).where(User.email == email).values(role=role))
    await db.commit()
    return user


async def admin(client: AsyncClient, db: AsyncSession, role: Role = Role.CONTENT_EDITOR) -> None:
    await as_role(client, db, role, f"{role.value}@example.com")


async def current_body(client: AsyncClient, slug: str = GATE) -> dict[str, Any]:
    res = await client.get(f"/admin/games/{slug}")
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()["body"]
    return body


async def test_learners_cannot_reach_admin(client: AsyncClient) -> None:
    await register(client)
    for path in ("/admin/content", f"/admin/games/{GATE}", "/admin/users"):
        res = await client.get(path)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "forbidden_role"


async def test_content_tree_lists_every_game(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    levels = (await client.get("/admin/content")).json()["levels"]
    assert [lv["slug"] for lv in levels] == [
        "academy",
        "signal-tower",
        "router-station",
        "gatehouse",
    ]
    gate = levels[3]["topics"][0]
    assert [g["slug"] for g in gate["games"]] == ["ticket-booth", "badge-check", "signup-gate"]
    assert gate["games"][0] == {
        "slug": "ticket-booth",
        "title": "Ticket Booth",
        "game_type": "bouncer",
        "is_checkpoint": False,
        "status": "published",
        "current_version": 1,
        "latest_version": 1,
    }


async def test_admin_sees_server_only_fields(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    game = (await client.get("/admin/games/signup-gate")).json()
    assert game["body"]["reference_solution"]
    assert game["body"]["hidden_tests"] == {"generator": "signup_boundaries"}
    assert game["versions"] == [
        {
            "version": 1,
            "created_at": game["versions"][0]["created_at"],
            "created_by": None,
            "is_current": True,
        }
    ]


async def test_saved_edit_is_a_draft_until_published(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    body = await current_body(client)
    body["title"] = "Ticket Booth, revised"
    saved = await client.post(f"/admin/games/{GATE}/versions", json=body)
    assert saved.status_code == 201, saved.text
    assert saved.json()["version"] == 2
    assert saved.json()["is_current"] is False
    assert saved.json()["versions"][0]["created_by"] == "content_editor@example.com"

    learner_view = (await client.get(f"/games/{GATE}/variant")).json()
    assert learner_view["version"] == 1
    assert learner_view["title"] == "Ticket Booth"

    published = await client.post(f"/admin/games/{GATE}/publish", json={"version": 2})
    assert published.status_code == 200, published.text
    learner_view = (await client.get(f"/games/{GATE}/variant")).json()
    assert learner_view["version"] == 2
    assert learner_view["title"] == "Ticket Booth, revised"

    # the seed sync never overwrites a version an admin published
    await sync(db)
    assert (await client.get(f"/games/{GATE}/variant")).json()["version"] == 2


async def test_attempt_keeps_its_version_after_a_publish(
    client: AsyncClient, db: AsyncSession
) -> None:
    await admin(client, db)
    old = await catalog.published_game(db, "signup-gate")
    assert old is not None
    token = (
        await client.get("/games/signup-gate/variant", params={"seed": 9, "mode": "checkpoint"})
    ).json()["attempt_token"]

    body = await current_body(client, "signup-gate")
    body["rules"] = [*body["rules"], "One more rule for v2."]
    await client.post("/admin/games/signup-gate/versions", json=body)
    assert (
        await client.post("/admin/games/signup-gate/publish", json={"version": 2})
    ).status_code == 200

    snippet = render(old.reference_solution, pick_params(old, 9).params)
    res = await client.post(
        "/games/signup-gate/grade", json={"attempt_token": token, "snippet": snippet}
    )
    assert res.status_code == 200
    assert res.json()["score"] == 100


async def test_test_run_shows_every_request(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    ok = (
        await client.post("/admin/games/signup-gate/test-run", json={"version": 1, "seed": 5})
    ).json()
    assert ok["issues"] == []
    assert ok["score"] == 100
    assert ok["starter_score"] < 70
    assert sum(c["hidden"] for c in ok["cases"]) == 12

    wrong = (
        await client.post(
            "/admin/games/signup-gate/test-run",
            json={"version": 1, "seed": 5, "snippet": "x: int = 1"},
        )
    ).json()
    assert wrong["passed"] is False


async def test_publish_is_blocked_when_the_reference_fails(
    client: AsyncClient, db: AsyncSession
) -> None:
    await admin(client, db)
    body = await current_body(client)
    body["reference_solution"] = "{{count_field}}: int\nrow: int\n"  # validates nothing
    await client.post(f"/admin/games/{GATE}/versions", json=body)
    res = await client.post(f"/admin/games/{GATE}/publish", json={"version": 2})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "publish_blocked"
    assert (await client.get(f"/games/{GATE}/variant")).json()["version"] == 1


async def test_broken_content_is_rejected_on_save(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    body = await current_body(client)
    body["starter_code"] = body["starter_code"].replace("# >>> EDIT START", "")
    body["rules"] = ["Uses {{nope}}"]
    res = await client.post(f"/admin/games/{GATE}/versions", json=body)
    assert res.status_code == 400
    message = res.json()["error"]["message"]
    assert "edit markers" in message
    assert "nope" in message


async def test_draft_status_hides_a_game(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    res = await client.patch(f"/admin/games/{GATE}", json={"status": "draft"})
    assert res.status_code == 200
    assert (await client.get(f"/games/{GATE}/variant")).status_code == 404


async def test_topic_settings(client: AsyncClient, db: AsyncSession) -> None:
    await admin(client, db)
    res = await client.patch(
        "/admin/topics/validate-signups",
        json={"pass_threshold": 80, "retest_cooldown_minutes": 5, "hints_allowed": False},
    )
    assert res.status_code == 200
    variant = (await client.get("/games/signup-gate/variant")).json()
    assert variant["pass_threshold"] == 80
    assert variant["hint_tiers"] == []


async def test_user_list_and_detail(client: AsyncClient, db: AsyncSession) -> None:
    await register(client, "learner-one@example.com")
    await client.post("/me/progress/lessons/python-for-js")
    await admin(client, db)
    listing = (await client.get("/admin/users", params={"q": "learner-one"})).json()
    assert listing["total"] == 1
    row = listing["users"][0]
    assert row["topics_passed"] == 1
    detail = (await client.get(f"/admin/users/{row['id']}")).json()
    assert detail["user"]["email"] == "learner-one@example.com"
    academy = next(t for t in detail["progress"]["topics"] if t["topic"] == "python-for-js")
    assert academy["complete"] is True


async def test_account_actions_need_super_admin(client: AsyncClient, db: AsyncSession) -> None:
    target = await register(client, "target@example.com")
    await admin(client, db, Role.CONTENT_EDITOR)
    res = await client.post(f"/admin/users/{target['id']}/block", json={"blocked": True})
    assert res.status_code == 403


async def test_super_admin_blocks_and_resets(client: AsyncClient, db: AsyncSession) -> None:
    target = await register(client, "target@example.com")
    await client.post("/me/progress/lessons/python-for-js")
    boss = await as_role(client, db, Role.SUPER_ADMIN, "boss@example.com")
    blocked = await client.post(f"/admin/users/{target['id']}/block", json={"blocked": True})
    assert blocked.json()["user"]["is_blocked"] is True
    reset = (await client.post(f"/admin/users/{target['id']}/reset")).json()
    assert reset["user"]["topics_passed"] == 0
    assert reset["attempts"] == []
    me = await client.post(f"/admin/users/{boss['id']}/block", json={"blocked": True})
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "self_action"


async def test_admin_sees_interest_per_track(client: AsyncClient, db: AsyncSession) -> None:
    await register(client, "fan@example.com")
    await client.post("/me/interests", json={"track": "frontend"})
    await admin(client, db)
    tracks = (await client.get("/admin/content")).json()["tracks"]
    by_slug = {t["slug"]: t for t in tracks}
    assert by_slug["frontend"]["interested"] == 1
    assert by_slug["full-stack"]["interested"] == 0
    assert by_slug["python-backend"]["status"] == "published"
