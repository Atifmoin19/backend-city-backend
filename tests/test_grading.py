import pytest
from httpx import AsyncClient

from app.core.security import create_attempt_token
from app.games.content import get_game
from app.games.variants import pick_params, render
from app.services.grading_service import grade

SLUG = "signup-gate"


def reference_snippet(seed: int) -> str:
    game = get_game(SLUG)
    assert game is not None
    return render(game.reference_solution, pick_params(game, seed).params)


@pytest.mark.parametrize("seed", [1, 42, 1337, 99999])
async def test_reference_solution_scores_100(seed: int) -> None:
    result = await grade(SLUG, create_attempt_token(SLUG, seed), reference_snippet(seed))
    assert result.verdict == "graded"
    assert result.score == 100
    assert result.passed
    assert result.stars == 3
    assert result.hidden_passed == result.hidden_total > 0


async def test_unvalidated_starter_fails() -> None:
    seed = 42
    params = pick_params(get_game(SLUG), seed).params  # type: ignore[arg-type]
    naive = f"{params['field_name']}: str\n{params['age_field']}: int\n"
    result = await grade(SLUG, create_attempt_token(SLUG, seed), naive)
    assert result.verdict == "graded"
    assert not result.passed
    assert result.score < 70


async def test_partial_solution_gets_partial_score() -> None:
    seed = 42
    params = pick_params(get_game(SLUG), seed).params  # type: ignore[arg-type]
    only_age = (
        f"{params['field_name']}: str\n"
        f"{params['age_field']}: int = Field(ge={params['min_age']}, le={params['max_age']})\n"
    )
    result = await grade(SLUG, create_attempt_token(SLUG, seed), only_age)
    assert 0 < result.score < 100


async def test_seed_from_token_not_client() -> None:
    """Solution for seed A must not pass a token for seed B with different params."""
    a, b = 1, 2
    game = get_game(SLUG)
    assert game is not None
    assert pick_params(game, a).params != pick_params(game, b).params
    result = await grade(SLUG, create_attempt_token(SLUG, b), reference_snippet(a))
    assert result.score < 100


async def test_blocked_snippet_is_rejected_without_running() -> None:
    result = await grade(SLUG, create_attempt_token(SLUG, 1), "import os\nos.system('ls')")
    assert result.verdict == "rejected"
    assert result.violations


async def test_variant_endpoint_never_leaks_server_only_fields(client: AsyncClient) -> None:
    res = await client.get(f"/games/{SLUG}/variant", params={"seed": 7})
    assert res.status_code == 200
    raw = res.text
    assert "reference_solution" not in raw
    assert "hidden" not in raw
    assert "Field(ge=" not in raw  # neither the answer nor answer-shaped hints ship
    assert res.json()["hint_tiers"] == [1, 2, 3]


async def test_hint_endpoint_renders_variant(client: AsyncClient) -> None:
    variant = (await client.get(f"/games/{SLUG}/variant", params={"seed": 7})).json()
    age_field = pick_params(get_game(SLUG), 7).params["age_field"]  # type: ignore[arg-type]
    res = await client.post(
        f"/games/{SLUG}/hint", json={"attempt_token": variant["attempt_token"], "tier": 3}
    )
    assert res.status_code == 200
    assert res.json()["text"].startswith(f"Something like: {age_field}: int")


async def test_grade_endpoint_requires_login(client: AsyncClient) -> None:
    res = await client.post(f"/games/{SLUG}/grade", json={"attempt_token": "x" * 20, "snippet": ""})
    assert res.status_code == 401


async def test_grade_endpoint_end_to_end(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "g@example.com", "password": "grading-pass-1", "display_name": "Grader"},
    )
    variant = (await client.get(f"/games/{SLUG}/variant", params={"seed": 5})).json()
    res = await client.post(
        f"/games/{SLUG}/grade",
        json={"attempt_token": variant["attempt_token"], "snippet": reference_snippet(5)},
    )
    assert res.status_code == 200
    assert res.json()["passed"] is True


async def test_grade_rejects_token_for_other_game(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "h@example.com", "password": "grading-pass-1", "display_name": "Hacker"},
    )
    token = create_attempt_token("some-other-game", 5)
    res = await client.post(f"/games/{SLUG}/grade", json={"attempt_token": token, "snippet": ""})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "attempt_invalid"
