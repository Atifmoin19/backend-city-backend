import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.models.user import User


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, item: Feedback) -> None:
        self.session.add(item)

    async def get(self, feedback_id: uuid.UUID) -> Feedback | None:
        return await self.session.get(Feedback, feedback_id)

    async def list(self, status: str | None, limit: int) -> list[tuple[Feedback, User | None]]:
        stmt = (
            select(Feedback, User)
            .outerjoin(User, User.id == Feedback.user_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Feedback.status == status)
        return [(f, u) for f, u in await self.session.execute(stmt)]

    async def counts(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(Feedback.status, func.count()).group_by(Feedback.status)
        )
        return {status: int(n) for status, n in rows}
