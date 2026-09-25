from app.core.errors import AppError, NotFoundError
from app.core.security import create_attempt_token, decode_attempt_token
from app.games.content import GameContent, get_game
from app.games.variants import Variant, new_seed, pick_params, render, render_json
from app.schemas.games import GameVariantPublic, Hint
from harness import HARNESS_VERSION


def require_game(slug: str) -> GameContent:
    game = get_game(slug)
    if game is None:
        raise NotFoundError(f"Game {slug!r} not found", code="game_not_found")
    return game


def public_variant(slug: str, seed: int | None = None) -> GameVariantPublic:
    game = require_game(slug)
    variant = pick_params(game, seed if seed is not None else new_seed())
    return _to_public(game, variant)


def _to_public(game: GameContent, v: Variant) -> GameVariantPublic:
    p = v.params
    return GameVariantPublic(
        slug=game.slug,
        game_type=game.game_type,
        title=game.title,
        district=game.district,
        character=game.character,
        visualizer=game.visualizer,
        is_checkpoint=game.is_checkpoint,
        pass_threshold=game.pass_threshold,
        scenario={k: render(t, p) for k, t in game.scenario.items()},
        objective=render(game.objective, p),
        rules=[render(r, p) for r in game.rules],
        starter_code=render(game.starter_code, p),
        editable_region=dict(game.editable_region),
        public_tests=render_json(game.public_tests, p),
        hint_tiers=sorted(int(h["tier"]) for h in game.hints),
        dialogue=game.dialogue,
        seed=v.seed,
        attempt_token=create_attempt_token(game.slug, v.seed),
        harness_version=HARNESS_VERSION,
    )


def hint(slug: str, attempt_token: str, tier: int) -> Hint:
    """Rendered hint for the attempt's variant.

    TODO(phase-1): record usage on the persisted attempt so grading applies the hint penalty.
    """
    decoded = decode_attempt_token(attempt_token)
    if decoded is None or decoded[0] != slug:
        raise AppError("Attempt token invalid or expired", code="attempt_invalid")
    game = require_game(slug)
    match = next((h for h in game.hints if int(h["tier"]) == tier), None)
    if match is None:
        raise NotFoundError(f"No tier {tier} hint", code="hint_not_found")
    params = pick_params(game, decoded[1]).params
    return Hint(tier=tier, text=render(str(match["text"]), params))
