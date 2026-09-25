"""Tracks are the sides of Full Stack City (backend today; frontend and full stack soon)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.enums import ContentStatus
from app.models.track import Track
from app.models.user import User
from app.repositories.track_repository import TrackRepository
from app.schemas.tracks import InterestList, TrackPublic


def to_public(track: Track) -> TrackPublic:
    return TrackPublic(
        slug=track.slug,
        title=track.title,
        description=track.description,
        status="open" if track.status == ContentStatus.PUBLISHED else "coming_soon",
    )


class TrackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TrackRepository(session)

    async def tracks(self) -> list[TrackPublic]:
        return [to_public(t) for t in await self.repo.all()]

    async def _track(self, slug: str) -> Track:
        track = await self.repo.by_slug(slug)
        if track is None:
            raise NotFoundError(f"Track {slug!r} not found", code="track_not_found")
        return track

    async def interests(self, user: User) -> InterestList:
        return InterestList(tracks=await self.repo.interests_of(user.id))

    async def notify_me(self, user: User, slug: str) -> InterestList:
        track = await self._track(slug)
        await self.repo.add_interest(user.id, track.id)
        await self.session.commit()
        return await self.interests(user)

    async def choose_goal(self, user: User, slug: str) -> User:
        """The signup question. Choosing a track that isn't open yet also asks to be notified."""
        track = await self._track(slug)
        user.learning_goal = track.slug
        if track.status != ContentStatus.PUBLISHED:
            await self.repo.add_interest(user.id, track.id)
        await self.session.commit()
        return user
