from fastapi import APIRouter

from app.core.deps import SessionDep
from app.schemas.tracks import TrackPublic
from app.services.track_service import TrackService

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/tracks", response_model=list[TrackPublic])
async def tracks(session: SessionDep) -> list[TrackPublic]:
    """The sides of the city and whether each is open or coming soon (public)."""
    return await TrackService(session).tracks()
