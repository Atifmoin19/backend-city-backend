from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    AttemptClaims,
    AttemptMode,
    create_attempt_token,
    decode_attempt_token,
)
from app.games import catalog
from app.games.content import GameContent
from app.games.variants import Variant, new_seed, pick_params, render, render_json
from app.models.user import User
from app.schemas.games import GameVariantPublic, Hint
from app.services.progress_service import ProgressService
from harness import HARNESS_VERSION


async def require_game(session: AsyncSession, slug: str) -> GameContent:
    game = await catalog.published_game(session, slug)
    if game is None:
        raise NotFoundError(f"Game {slug!r} not found", code="game_not_found")
    return game


async def game_for_token(
    session: AsyncSession, slug: str, attempt_token: str
) -> tuple[GameContent, AttemptClaims]:
    """The exact version + variant an attempt token was issued for."""
    claims = decode_attempt_token(attempt_token)
    if claims is None or claims.game != slug:
        raise AppError("Attempt token invalid or expired", code="attempt_invalid")
    game = await catalog.game_version(session, claims.version_id)
    if game is None or game.slug != slug:
        raise AppError("Attempt token invalid or expired", code="attempt_invalid")
    return game, claims


async def public_variant(
    session: AsyncSession, slug: str, seed: int | None = None, mode: AttemptMode = "practice"
) -> GameVariantPublic:
    game = await require_game(session, slug)
    if mode == "checkpoint" and not game.is_checkpoint:
        raise AppError("This game is practice only", code="not_a_checkpoint")
    variant = pick_params(game, seed if seed is not None else new_seed())
    return to_public(game, variant, mode)


def to_public(game: GameContent, v: Variant, mode: AttemptMode) -> GameVariantPublic:
    p = v.params
    return GameVariantPublic(
        slug=game.slug,
        mode=mode,
        version=game.version,
        topic=game.topic_slug,
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
        editable_region={
            "start_marker": game.editable_region["start_marker"],
            "end_marker": game.editable_region["end_marker"],
        },
        public_tests=render_json(game.public_tests, p),
        hint_tiers=sorted(int(h["tier"]) for h in game.hints) if game.hints_allowed else [],
        dialogue=game.dialogue,
        seed=v.seed,
        attempt_token=create_attempt_token(game.slug, v.seed, game.version_id, mode),
        harness_version=HARNESS_VERSION,
    )


async def hint(
    session: AsyncSession, slug: str, attempt_token: str, tier: int, user: User | None
) -> Hint:
    """Rendered hint for the attempt's variant. Checkpoint hints need a login: they are
    counted on the attempt and lower its maximum score."""
    game, claims = await game_for_token(session, slug, attempt_token)
    if not game.hints_allowed:
        raise ForbiddenError("Hints are turned off for this topic", code="hints_disabled")
    match = next((h for h in game.hints if int(h["tier"]) == tier), None)
    if match is None:
        raise NotFoundError(f"No tier {tier} hint", code="hint_not_found")
    if claims.mode == "checkpoint":
        if user is None:
            raise UnauthorizedError("Log in to use hints on a checkpoint", code="not_authenticated")
        await ProgressService(session).record_hint(user, game, claims.seed, tier)
    params = pick_params(game, claims.seed).params
    return Hint(tier=tier, text=render(str(match["text"]), params))
