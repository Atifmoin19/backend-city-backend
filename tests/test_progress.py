from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.games import catalog
from app.games.variants import pick_params, render
from app.models.topic import Topic
from app.repositories.content_repository import ContentRepository
from tests.conftest import register

GATE = "signup-gate"


def topic_of(progress: dict[str, Any], slug: str) -> dict[str, Any]:
    return next(t for t in progress["topics"] if t["topic"] == slug)


async def progress(client: AsyncClient, **params: str) -> dict[str, Any]:
    res = await client.get("/me/progress", params=params)
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


async def submit(client: AsyncClient, db: AsyncSession, seed: int, correct: bool) -> dict[str, Any]:
    game = await catalog.published_game(db, GATE)
    assert game is not None
    variant = (
        await client.get(f"/games/{GATE}/variant", params={"seed": seed, "mode": "checkpoint"})
    ).json()
    params = pick_params(game, seed).params
    snippet = (
        render(game.reference_solution, params)
        if correct
        else f"{params['field_name']}: str\n{params['age_field']}: int\n"
    )
    res = await client.post(
        f"/games/{GATE}/grade", json={"attempt_token": variant["attempt_token"], "snippet": snippet}
    )
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


async def test_progress_needs_login(client: AsyncClient) -> None:
    assert (await client.get("/me/progress")).status_code == 401


async def test_new_learner_sees_every_topic_locked(client: AsyncClient) -> None:
    await register(client)
    body = await progress(client)
    assert body["onboarded"] is False
    gate = topic_of(body, "validate-signups")
    assert gate["status"] == "locked"
    assert gate["checkpoint_game"] == GATE
    assert gate["track"] == "python-backend"
    assert gate["complete"] is False


async def test_track_filter(client: AsyncClient) -> None:
    await register(client)
    assert (await progress(client, track="python-backend"))["topics"]
    assert (await progress(client, track="frontend"))["topics"] == []


async def test_lesson_only_topic_completes_on_briefing(client: AsyncClient) -> None:
    await register(client)
    res = await client.post("/me/progress/lessons/python-for-js")
    assert res.status_code == 200
    body = res.json()
    assert body["lesson_done"] is True
    assert body["complete"] is True
    assert body["status"] == "passed"


async def test_lesson_does_not_complete_a_topic_with_a_checkpoint(client: AsyncClient) -> None:
    await register(client)
    body = (await client.post("/me/progress/lessons/validate-signups")).json()
    assert body["lesson_done"] is True
    assert body["complete"] is False
    assert body["status"] == "unlocked"


async def test_unknown_topic_is_404(client: AsyncClient) -> None:
    await register(client)
    res = await client.post("/me/progress/lessons/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "topic_not_found"


async def test_practice_pass_is_recorded_once_and_never_taken_back(client: AsyncClient) -> None:
    await register(client)
    variant = (await client.get(f"/games/{GATE}/variant", params={"seed": 3})).json()
    token = variant["attempt_token"]
    ok = await client.post(
        f"/games/{GATE}/practice", json={"attempt_token": token, "passed": True, "score": 100}
    )
    assert ok.status_code == 200
    again = await client.post(
        f"/games/{GATE}/practice", json={"attempt_token": token, "passed": False, "score": 0}
    )
    assert again.status_code == 200
    # signup-gate is the checkpoint; its practice runs are extra practice, not required games
    assert again.json()["practice_passed"] == []


async def test_checkpoint_pass_completes_the_topic(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    fail = await submit(client, db, 11, correct=False)
    assert fail["passed"] is False
    gate = topic_of(await progress(client), "validate-signups")
    assert gate["consecutive_fails"] == 1
    assert gate["checkpoint"]["attempts"] == 1
    assert gate["complete"] is False

    win = await submit(client, db, 12, correct=True)
    assert win["passed"] is True
    gate = topic_of(await progress(client), "validate-signups")
    assert gate["complete"] is True
    assert gate["status"] == "passed"
    assert gate["checkpoint"] == {
        "best_score": 100,
        "stars": 3,
        "attempts": 2,
        "passed": True,
        "passed_at": gate["checkpoint"]["passed_at"],
    }
    assert gate["consecutive_fails"] == 0


async def test_retest_cooldown_after_a_fail(client: AsyncClient, db: AsyncSession) -> None:
    topic = await ContentRepository(db).topic_by_slug("validate-signups")
    assert isinstance(topic, Topic)
    topic.retest_cooldown_minutes = 10
    await db.commit()
    await register(client)

    fail = await submit(client, db, 21, correct=False)
    assert fail["retry_at"] is not None
    assert topic_of(await progress(client), "validate-signups")["retry_at"] is not None

    variant = (
        await client.get(f"/games/{GATE}/variant", params={"seed": 22, "mode": "checkpoint"})
    ).json()
    res = await client.post(
        f"/games/{GATE}/grade", json={"attempt_token": variant["attempt_token"], "snippet": "x = 1"}
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "retest_cooldown"


async def test_onboarded_flag_rides_on_the_user(client: AsyncClient) -> None:
    await register(client)
    assert (await client.get("/auth/me")).json()["onboarded"] is False
    assert (await client.post("/me/onboarded")).status_code == 204
    assert (await client.get("/auth/me")).json()["onboarded"] is True


async def test_import_moves_lessons_and_orientation_only(client: AsyncClient) -> None:
    await register(client)
    res = await client.post(
        "/me/progress/import",
        json={
            "onboarded": True,
            "lessons_done": ["python-for-js", "validate-signups", "no-such-topic"],
            "checkpoints": {"validate-signups": {"score": 100, "stars": 3}},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["onboarded"] is True
    assert topic_of(body, "python-for-js")["complete"] is True
    gate = topic_of(body, "validate-signups")
    assert gate["lesson_done"] is True
    assert gate["checkpoint"] is None  # checkpoints only count when graded on the server
    assert gate["complete"] is False


async def test_tracks_list_open_and_coming_soon(client: AsyncClient) -> None:
    tracks = (await client.get("/content/tracks")).json()
    assert [(t["slug"], t["status"]) for t in tracks] == [
        ("python-backend", "open"),
        ("frontend", "coming_soon"),
        ("full-stack", "coming_soon"),
    ]


async def test_choosing_a_coming_soon_goal_records_interest(client: AsyncClient) -> None:
    await register(client)
    res = await client.put("/me/goal", json={"track": "frontend"})
    assert res.status_code == 200
    assert res.json()["learning_goal"] == "frontend"
    assert (await client.get("/auth/me")).json()["learning_goal"] == "frontend"
    assert (await client.get("/me/interests")).json() == {"tracks": ["frontend"]}


async def test_notify_me_is_idempotent(client: AsyncClient) -> None:
    await register(client)
    for _ in range(2):
        res = await client.post("/me/interests", json={"track": "full-stack"})
    assert res.json() == {"tracks": ["full-stack"]}
    assert (await client.post("/me/interests", json={"track": "nope"})).status_code == 404


async def test_open_goal_is_not_an_interest(client: AsyncClient) -> None:
    await register(client)
    await client.put("/me/goal", json={"track": "python-backend"})
    assert (await client.get("/me/interests")).json() == {"tracks": []}
