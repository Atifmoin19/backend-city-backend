from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.config import get_settings
from app.core.deps import CurrentUser
from app.core.rate_limit import limiter
from app.games.variants import MAX_SEED
from app.schemas.games import GameVariantPublic, GradeRequest, GradeResponse, Hint, HintRequest
from app.services import game_service, grading_service

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/{slug}/variant", response_model=GameVariantPublic)
async def get_variant(
    slug: str, seed: Annotated[int | None, Query(ge=1, le=MAX_SEED)] = None
) -> GameVariantPublic:
    """Public game payload for one variant. Practice can run fully in the browser from this."""
    return game_service.public_variant(slug, seed)


@router.post("/{slug}/grade", response_model=GradeResponse)
@limiter.limit(get_settings().checkpoint_rate_limit)
async def grade(request: Request, slug: str, body: GradeRequest, _: CurrentUser) -> GradeResponse:
    """Server-side checkpoint grading with hidden tests (ideology §11.3)."""
    return await grading_service.grade(slug, body.attempt_token, body.snippet)


@router.post("/{slug}/hint", response_model=Hint)
@limiter.limit(get_settings().checkpoint_rate_limit)
async def get_hint(request: Request, slug: str, body: HintRequest) -> Hint:
    return game_service.hint(slug, body.attempt_token, body.tier)
