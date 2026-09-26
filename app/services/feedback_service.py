import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.feedback import Feedback
from app.models.user import User
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import AdminFeedback, AdminFeedbackList, FeedbackIn, FeedbackStatus


def _admin_view(f: Feedback, u: User | None) -> AdminFeedback:
    return AdminFeedback(
        id=f.id,
        kind=f.kind,
        message=f.message,
        page=f.page,
        game_slug=f.game_slug,
        status=f.status,
        created_at=f.created_at,
        user_id=f.user_id,
        user_email=u.email if u else None,
        user_name=u.display_name if u else None,
    )


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FeedbackRepository(session)

    async def send(self, user: User, body: FeedbackIn) -> None:
        self.repo.add(
            Feedback(
                user_id=user.id,
                kind=body.kind,
                message=body.message.strip(),
                page=body.page,
                game_slug=body.game_slug,
            )
        )
        await self.session.commit()

    async def inbox(self, status: FeedbackStatus | None, limit: int = 200) -> AdminFeedbackList:
        rows = await self.repo.list(status, limit)
        counts = {"new": 0, "seen": 0, "done": 0, **await self.repo.counts()}
        return AdminFeedbackList(items=[_admin_view(f, u) for f, u in rows], counts=counts)

    async def set_status(self, feedback_id: uuid.UUID, status: FeedbackStatus) -> AdminFeedback:
        item = await self.repo.get(feedback_id)
        if item is None:
            raise NotFoundError("Feedback not found", code="feedback_not_found")
        item.status = status
        await self.session.commit()
        user = await self.session.get(User, item.user_id) if item.user_id else None
        return _admin_view(item, user)
