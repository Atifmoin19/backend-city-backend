"""Admin analytics and the feedback inbox."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import register
from tests.test_admin import admin
from tests.test_progress import submit


async def test_feedback_goes_to_the_admin_inbox(client: AsyncClient, db: AsyncSession) -> None:
    assert (
        await client.post("/me/feedback", json={"kind": "bug", "message": "x"})
    ).status_code == 401
    await register(client)
    bad = await client.post("/me/feedback", json={"kind": "rant", "message": "hello"})
    assert bad.status_code == 422
    sent = await client.post(
        "/me/feedback",
        json={"kind": "content", "message": "  Rule 2 is unclear  ", "game_slug": "badge-check"},
    )
    assert sent.status_code == 204
    assert (await client.get("/admin/feedback")).status_code == 403  # learners can't read it

    await admin(client, db)
    inbox = (await client.get("/admin/feedback")).json()
    assert inbox["counts"] == {"new": 1, "seen": 0, "done": 0}
    item = inbox["items"][0]
    assert item["message"] == "Rule 2 is unclear"
    assert item["user_email"] == "learner@example.com"
    assert item["game_slug"] == "badge-check"

    done = await client.patch(f"/admin/feedback/{item['id']}", json={"status": "done"})
    assert done.json()["status"] == "done"
    assert (await client.get("/admin/feedback", params={"status": "new"})).json()["items"] == []


async def test_analytics_funnel_and_hardest_games(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    await client.post("/me/progress/lessons/validate-signups")
    variant = (await client.get("/games/badge-check/variant", params={"seed": 3})).json()
    await client.post(
        "/games/badge-check/practice",
        json={"attempt_token": variant["attempt_token"], "passed": True, "score": 100},
    )
    await submit(client, db, 11, correct=False)
    await submit(client, db, 12, correct=True)
    await client.post(
        "/me/quiz-results", json={"quiz": "pick-the-line-gate", "score": 4, "total": 5}
    )

    await admin(client, db)
    res = await client.get("/admin/analytics")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["learners"]["total"] == 2
    assert len(body["learners"]["signups_14d"]) == 14
    assert body["learners"]["signups_14d"][-1]["count"] == 2

    funnel = {row["topic"]: row for row in body["funnel"]}
    gate = funnel["validate-signups"]
    assert (gate["briefed"], gate["practiced"], gate["attempted"], gate["passed"]) == (1, 1, 1, 1)
    academy = funnel["python-for-js"]
    assert academy["attempted"] is None and academy["passed"] is None  # lesson-only

    games = {g["slug"]: g for g in body["games"]}
    assert games["signup-gate"]["attempts"] == 2
    assert games["signup-gate"]["pass_rate"] == 0.5
    assert games["badge-check"]["pass_rate"] == 1.0
    assert body["games"][0]["slug"] == "signup-gate"  # hardest played game first
    assert body["quizzes"] == [
        {"quiz": "pick-the-line-gate", "rounds": 1, "players": 1, "avg_pct": 80.0}
    ]
