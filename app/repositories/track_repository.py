import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interest import TrackInterest
from app.models.track import Track


class TrackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all(self) -> list[Track]:
        result = await self.session.execute(select(Track).order_by(Track.order, Track.slug))
        return list(result.scalars())

    async def by_slug(self, slug: str) -> Track | None:
        result = await self.session.execute(select(Track).where(Track.slug == slug))
        return result.scalar_one_or_none()

    async def add_interest(self, user_id: uuid.UUID, track_id: uuid.UUID) -> None:
        stmt = insert(TrackInterest).values(user_id=user_id, track_id=track_id)
        await self.session.execute(stmt.on_conflict_do_nothing())

    async def interests_of(self, user_id: uuid.UUID) -> list[str]:
        result = await self.session.execute(
            select(Track.slug)
            .join(TrackInterest, TrackInterest.track_id == Track.id)
            .where(TrackInterest.user_id == user_id)
            .order_by(Track.order)
        )
        return list(result.scalars())

    async def interest_counts(self) -> dict[uuid.UUID, int]:
        result = await self.session.execute(
            select(TrackInterest.track_id, func.count()).group_by(TrackInterest.track_id)
        )
        return {track_id: int(n) for track_id, n in result}
