from httpx import AsyncClient

from tests.conftest import register


async def test_quiz_results_keep_the_best_round(client: AsyncClient) -> None:
    await register(client)
    for score, combo in [(6, 3), (9, 5), (8, 8)]:
        res = await client.post(
            "/me/quiz-results",
            json={"quiz": "status-speed-round", "score": score, "total": 10, "best_combo": combo},
        )
        assert res.status_code == 201, res.text
    await client.post("/me/quiz-results", json={"quiz": "pick-the-line", "score": 2, "total": 5})
    results = (await client.get("/me/quiz-results")).json()["results"]
    assert all(r.pop("last_played_at") for r in results)
    assert results == [
        {"quiz": "pick-the-line", "best_score": 2, "total": 5, "best_combo": 0, "plays": 1},
        {"quiz": "status-speed-round", "best_score": 9, "total": 10, "best_combo": 5, "plays": 3},
    ]


async def test_quiz_results_are_validated_and_private(client: AsyncClient) -> None:
    assert (await client.get("/me/quiz-results")).status_code == 401
    await register(client)
    bad = [
        {"quiz": "x", "score": 11, "total": 10},
        {"quiz": "x", "score": 1, "total": 10, "best_combo": 11},
        {"quiz": "../etc", "score": 1, "total": 10},
    ]
    for body in bad:
        assert (await client.post("/me/quiz-results", json=body)).status_code == 422


async def test_placement_saves_a_known_district(client: AsyncClient) -> None:
    await register(client)
    res = await client.put("/me/placement", json={"start_district": "router-station"})
    assert res.status_code == 200
    assert res.json()["start_district"] == "router-station"
    assert (await client.get("/auth/me")).json()["start_district"] == "router-station"
    missing = await client.put("/me/placement", json={"start_district": "moon-base"})
    assert missing.status_code == 404
