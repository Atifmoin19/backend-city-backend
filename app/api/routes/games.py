from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.config import get_settings
from app.core.deps import CurrentUser, OptionalUser, SessionDep
from app.core.rate_limit import limiter, user_or_ip
from app.core.security import AttemptMode
from app.games.variants import MAX_SEED
from app.schemas.games import GameVariantPublic, GradeRequest, GradeResponse, Hint, HintRequest
from app.schemas.progress import PracticeRequest, TopicProgressPublic
from app.services import game_service, grading_service
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/games", tags=["games"])
_limit = get_settings().checkpoint_rate_limit


@router.get("/{slug}/variant", response_model=GameVariantPublic)
async def get_variant(
    slug: str,
    session: SessionDep,
    seed: Annotated[int | None, Query(ge=1, le=MAX_SEED)] = None,
    mode: AttemptMode = "practice",
) -> GameVariantPublic:
    """Public game payload for one variant. Practice can run fully in the browser from this."""
    return await game_service.public_variant(session, slug, seed, mode)


@router.post("/{slug}/grade", response_model=GradeResponse)
@limiter.limit(_limit, key_func=user_or_ip)
async def grade(
    request: Request, slug: str, body: GradeRequest, session: SessionDep, user: CurrentUser
) -> GradeResponse:
    """Server-side checkpoint grading with hidden tests (ideology §11.3). Saves the attempt."""
    return await grading_service.grade(session, slug, body.attempt_token, body.snippet, user)


@router.post("/{slug}/hint", response_model=Hint)
@limiter.limit(_limit, key_func=user_or_ip)
async def get_hint(
    request: Request, slug: str, body: HintRequest, session: SessionDep, user: OptionalUser
) -> Hint:
    return await game_service.hint(session, slug, body.attempt_token, body.tier, user)


@router.post("/{slug}/practice", response_model=TopicProgressPublic)
@limiter.limit(_limit, key_func=user_or_ip)
async def record_practice(
    request: Request, slug: str, body: PracticeRequest, session: SessionDep, user: CurrentUser
) -> TopicProgressPublic:
    """Save a practice result (runs in the browser, so self-reported and low stakes)."""
    game, claims = await game_service.game_for_token(session, slug, body.attempt_token)
    return await ProgressService(session).record_practice(
        user, game, claims.seed, body.passed, body.score
    )
