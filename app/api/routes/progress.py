from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.progress import ProgressImport, ProgressPublic, TopicProgressPublic
from app.services.progress_service import ProgressService

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
