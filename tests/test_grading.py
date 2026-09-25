import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_attempt_token
from app.games import catalog
from app.games.content import GameContent
from app.games.variants import pick_params, render
from app.schemas.games import GradeResponse
from app.services.grading_service import run_checks
from tests.conftest import register

SLUG = "signup-gate"


async def game(db: AsyncSession, slug: str = SLUG) -> GameContent:
    g = await catalog.published_game(db, slug)
    assert g is not None
    return g


def reference_snippet(g: GameContent, seed: int) -> str:
    return render(g.reference_solution, pick_params(g, seed).params)


async def check(g: GameContent, seed: int, snippet: str, hints: int = 0) -> GradeResponse:
    return await run_checks(g, pick_params(g, seed), snippet, g.pass_threshold, hints)


async def checkpoint_variant(client: AsyncClient, seed: int, slug: str = SLUG) -> dict[str, object]:
    res = await client.get(f"/games/{slug}/variant", params={"seed": seed, "mode": "checkpoint"})
    assert res.status_code == 200, res.text
    body: dict[str, object] = res.json()
    return body


@pytest.mark.parametrize("seed", [1, 42, 1337, 99999])
async def test_reference_solution_scores_100(db: AsyncSession, seed: int) -> None:
    g = await game(db)
    result = await check(g, seed, reference_snippet(g, seed))
    assert result.verdict == "graded"
    assert result.score == 100
    assert result.passed
    assert result.stars == 3
    assert result.hidden_passed == result.hidden_total > 0


async def test_indented_snippet_from_editor_is_accepted(db: AsyncSession) -> None:
    """The editor sends the region with its class-body indentation."""
    g = await game(db)
    indented = "".join(f"    {line}\n" for line in reference_snippet(g, 42).splitlines())
    result = await check(g, 42, indented)
    assert result.verdict == "graded"
    assert result.score == 100


async def test_unvalidated_starter_fails(db: AsyncSession) -> None:
    g = await game(db)
    params = pick_params(g, 42).params
    naive = f"{params['field_name']}: str\n{params['age_field']}: int\n"
    result = await check(g, 42, naive)
    assert result.verdict == "graded"
    assert not result.passed
    assert result.score < 70


async def test_partial_solution_gets_partial_score(db: AsyncSession) -> None:
    g = await game(db)
    params = pick_params(g, 42).params
    only_age = (
        f"{params['field_name']}: str\n"
        f"{params['age_field']}: int = Field(ge={params['min_age']}, le={params['max_age']})\n"
    )
    result = await check(g, 42, only_age)
    assert 0 < result.score < 100


async def test_hints_lower_the_score_and_the_stars(db: AsyncSession) -> None:
    g = await game(db)
    result = await check(g, 7, reference_snippet(g, 7), hints=2)
    assert result.raw_score == 100
    assert result.hint_penalty == 10
    assert result.score == 90
    assert result.stars == 2  # 3 stars need no hints


async def test_seed_from_token_not_client(db: AsyncSession) -> None:
    """Solution for seed A must not pass seed B with different params."""
    g = await game(db)
    assert pick_params(g, 1).params != pick_params(g, 2).params
    result = await check(g, 2, reference_snippet(g, 1))
    assert result.score < 100


async def test_blocked_snippet_is_rejected_without_running(db: AsyncSession) -> None:
    result = await check(await game(db), 1, "import os\nos.system('ls')")
    assert result.verdict == "rejected"
    assert result.violations


async def test_variant_endpoint_never_leaks_server_only_fields(client: AsyncClient) -> None:
    res = await client.get(f"/games/{SLUG}/variant", params={"seed": 7})
    assert res.status_code == 200
    raw = res.text
    assert "reference_solution" not in raw
    assert "hidden" not in raw
    assert "Field(ge=" not in raw  # neither the answer nor answer-shaped hints ship
    body = res.json()
    assert body["hint_tiers"] == [1, 2, 3]
    assert body["mode"] == "practice"
    assert body["topic"] == "validate-signups"
    assert body["district"] == "gatehouse"


async def test_variant_ships_rendered_objective_and_rules(
    client: AsyncClient, db: AsyncSession
) -> None:
    body = (await client.get(f"/games/{SLUG}/variant", params={"seed": 7})).json()
    params = pick_params(await game(db), 7).params
    assert body["objective"]
    assert len(body["rules"]) == 3
    assert all("{{" not in r for r in body["rules"])
    assert f"`{params['field_name']}`" in body["rules"][0]
    assert str(params["max_age"]) in body["rules"][1]


async def test_practice_hint_needs_no_login(client: AsyncClient, db: AsyncSession) -> None:
    variant = (await client.get(f"/games/{SLUG}/variant", params={"seed": 7})).json()
    age_field = pick_params(await game(db), 7).params["age_field"]
    res = await client.post(
        f"/games/{SLUG}/hint", json={"attempt_token": variant["attempt_token"], "tier": 3}
    )
    assert res.status_code == 200
    assert res.json()["text"].startswith(f"Something like: {age_field}: int")


async def test_checkpoint_hint_needs_login(client: AsyncClient) -> None:
    variant = await checkpoint_variant(client, 7)
    res = await client.post(
        f"/games/{SLUG}/hint", json={"attempt_token": variant["attempt_token"], "tier": 1}
    )
    assert res.status_code == 401


async def test_grade_endpoint_requires_login(client: AsyncClient) -> None:
    res = await client.post(f"/games/{SLUG}/grade", json={"attempt_token": "x" * 20, "snippet": ""})
    assert res.status_code == 401


async def test_grade_endpoint_end_to_end(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    variant = await checkpoint_variant(client, 5)
    res = await client.post(
        f"/games/{SLUG}/grade",
        json={
            "attempt_token": variant["attempt_token"],
            "snippet": reference_snippet(await game(db), 5),
        },
    )
    assert res.status_code == 200
    assert res.json()["passed"] is True


async def test_checkpoint_hints_are_charged_at_grading(
    client: AsyncClient, db: AsyncSession
) -> None:
    await register(client)
    variant = await checkpoint_variant(client, 5)
    token = variant["attempt_token"]
    for tier in (1, 2):
        res = await client.post(f"/games/{SLUG}/hint", json={"attempt_token": token, "tier": tier})
        assert res.status_code == 200
    res = await client.post(
        f"/games/{SLUG}/grade",
        json={"attempt_token": token, "snippet": reference_snippet(await game(db), 5)},
    )
    body = res.json()
    assert body["hints_used"] == 2
    assert body["score"] == 90
    assert body["stars"] == 2


async def test_practice_token_cannot_be_graded(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    variant = (await client.get(f"/games/{SLUG}/variant", params={"seed": 5})).json()
    res = await client.post(
        f"/games/{SLUG}/grade",
        json={
            "attempt_token": variant["attempt_token"],
            "snippet": reference_snippet(await game(db), 5),
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "attempt_invalid"


async def test_grade_rejects_token_for_other_game(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    token = create_attempt_token("some-other-game", 5, (await game(db)).version_id, "checkpoint")
    res = await client.post(f"/games/{SLUG}/grade", json={"attempt_token": token, "snippet": ""})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "attempt_invalid"
