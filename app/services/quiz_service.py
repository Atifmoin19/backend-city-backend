"""Quiz rounds and the placement result. Quizzes are revision drills graded in the browser
(like lesson checks); the server keeps scores and never gates progress on them."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.quiz import QuizResult
from app.models.user import User
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import PlacementIn, QuizResultIn, QuizResults


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = QuizRepository(session)

    async def results(self, user: User) -> QuizResults:
        return QuizResults(results=await self.repo.bests(user.id))

    async def record(self, user: User, body: QuizResultIn) -> QuizResults:
        self.repo.add(
            QuizResult(
                user_id=user.id,
                quiz_slug=body.quiz,
                score=body.score,
                total=body.total,
                best_combo=body.best_combo,
                seconds=body.seconds,
            )
        )
        await self.session.commit()
        return await self.results(user)

    async def set_placement(self, user: User, body: PlacementIn) -> User:
        if not await self.repo.district_exists(body.start_district):
            raise NotFoundError(
                f"District {body.start_district!r} not found", code="district_not_found"
            )
        user.start_district = body.start_district
        await self.session.commit()
        return user
