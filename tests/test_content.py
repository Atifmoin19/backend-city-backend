"""Every seeded game must be solvable by its reference solution and not by its starter code."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.games import catalog
from app.games.content import curriculum, seed_games
from app.games.registry import generator_for
from app.games.variants import pick_params, render, render_json
from app.services import game_service
from app.services.grading_service import run_checks
from harness.runner import run
from harness.splice import splice

GAMES = sorted(seed_games())
SEEDS = [1, 7, 42, 1337]


def test_curriculum_names_only_existing_games_once() -> None:
    placed = [
        g
        for level in curriculum().levels
        for chapter in level.chapters
        for topic in chapter.topics
        for g in [*topic.practice, *([topic.checkpoint] if topic.checkpoint else [])]
    ]
    assert sorted(placed) == GAMES


@pytest.mark.parametrize("slug", GAMES)
@pytest.mark.parametrize("seed", SEEDS)
async def test_reference_solution_passes_every_request(
    db: AsyncSession, slug: str, seed: int
) -> None:
    game = await catalog.published_game(db, slug)
    assert game is not None
    variant = pick_params(game, seed)
    result = await run_checks(
        game, variant, render(game.reference_solution, variant.params), game.pass_threshold
    )
    assert result.verdict == "graded", result.error
    assert result.score == 100, [r for r in result.public_results if not r.passed]
    if game.is_checkpoint:
        assert result.hidden_total >= 8  # a checkpoint probes more than the public requests


@pytest.mark.parametrize("slug", GAMES)
async def test_starter_code_does_not_pass(db: AsyncSession, slug: str) -> None:
    game = await catalog.published_game(db, slug)
    assert game is not None
    variant = pick_params(game, 42)
    starter = render(game.starter_code, variant.params)
    public = render_json(game.public_tests, variant.params)
    report = await run(starter, public)
    assert report["ok"], report["error"]
    assert not all(r["passed"] for r in report["results"])
    hidden = generator_for(game).hidden_tests(game, variant)
    full = await run(starter, public + hidden)
    passed = sum(r["passed"] for r in full["results"])
    assert 100 * passed / len(full["results"]) < game.pass_threshold


@pytest.mark.parametrize("slug", GAMES)
async def test_every_placeholder_is_filled(db: AsyncSession, slug: str) -> None:
    game = await catalog.published_game(db, slug)
    assert game is not None
    for seed in SEEDS:
        payload = (await game_service.public_variant(db, slug, seed)).model_dump_json()
        assert "{{" not in payload, payload
        p = pick_params(game, seed).params
        assert "{{" not in splice(
            render(game.starter_code, p), render(game.reference_solution, p), game.editable_region
        )
