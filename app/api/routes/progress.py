from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.auth import UserPublic
from app.schemas.progress import ProgressImport, ProgressPublic, TopicProgressPublic
from app.schemas.tracks import InterestList, TrackChoice
from app.services.progress_service import ProgressService
from app.services.track_service import TrackService

router = APIRouter(prefix="/me", tags=["progress"])


@router.get("/progress", response_model=ProgressPublic)
async def get_progress(
    user: CurrentUser, session: SessionDep, track: str | None = None
) -> ProgressPublic:
    """Every published topic with the learner's state. `track` narrows it to one city."""
    return await ProgressService(session).progress(user, track)


@router.post("/progress/lessons/{topic_slug}", response_model=TopicProgressPublic)
async def complete_lesson(
    topic_slug: str, user: CurrentUser, session: SessionDep
) -> TopicProgressPublic:
    return await ProgressService(session).complete_lesson(user, topic_slug)


@router.post("/progress/import", response_model=ProgressPublic)
async def import_progress(
    body: ProgressImport, user: CurrentUser, session: SessionDep
) -> ProgressPublic:
    """One-time move of browser-kept progress (lessons + orientation, never checkpoints)."""
    return await ProgressService(session).import_local(user, body)


@router.post("/onboarded", status_code=status.HTTP_204_NO_CONTENT)
async def onboarded(user: CurrentUser, session: SessionDep) -> None:
    await ProgressService(session).mark_onboarded(user)


@router.put("/goal", response_model=UserPublic)
async def choose_goal(body: TrackChoice, user: CurrentUser, session: SessionDep) -> UserPublic:
    """Which side of the city the learner wants (signup question). A coming-soon choice is
    also recorded as interest."""
    return UserPublic.model_validate(await TrackService(session).choose_goal(user, body.track))


@router.get("/interests", response_model=InterestList)
async def interests(user: CurrentUser, session: SessionDep) -> InterestList:
    return await TrackService(session).interests(user)


@router.post("/interests", response_model=InterestList)
async def notify_me(body: TrackChoice, user: CurrentUser, session: SessionDep) -> InterestList:
    """ "Notify me" for a track that isn't open yet. Idempotent."""
    return await TrackService(session).notify_me(user, body.track)
