import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.enums import TopicProgressStatus
from app.models.progress import TopicProgress
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    def _matching(self, q: str | None) -> Select[User]:
        stmt = select(User)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(or_(User.email.ilike(like), User.display_name.ilike(like)))
        return stmt

    async def search(self, q: str | None, limit: int, offset: int) -> list[User]:
        stmt = self._matching(q).order_by(User.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars())

    async def count(self, q: str | None) -> int:
        stmt = select(func.count()).select_from(self._matching(q).subquery())
        return int((await self.session.execute(stmt)).scalar_one())

    async def learning_stats(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """(topics passed, scored checkpoint attempts) per user."""
        passed = select(TopicProgress.user_id, func.count()).where(
            TopicProgress.user_id.in_(user_ids), TopicProgress.status == TopicProgressStatus.PASSED
        )
        tries = select(Attempt.user_id, func.count()).where(
            Attempt.user_id.in_(user_ids),
            Attempt.is_checkpoint.is_(True),
            Attempt.score.is_not(None),
        )
        out = {uid: (0, 0) for uid in user_ids}
        for uid, n in await self.session.execute(passed.group_by(TopicProgress.user_id)):
            out[uid] = (int(n), out[uid][1])
        for uid, n in await self.session.execute(tries.group_by(Attempt.user_id)):
            out[uid] = (out[uid][0], int(n))
        return out
