import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.level import Level
from app.models.quiz import QuizResult
from app.schemas.quiz import QuizBest


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, result: QuizResult) -> None:
        self.session.add(result)

    async def bests(self, user_id: uuid.UUID) -> list[QuizBest]:
        """Per quiz: the best round (highest share correct, then combo) and the play count."""
        ranked = (
            select(
                QuizResult.quiz_slug,
                QuizResult.score,
                QuizResult.total,
                QuizResult.best_combo,
                func.count().over(partition_by=QuizResult.quiz_slug).label("plays"),
                func.max(QuizResult.created_at)
                .over(partition_by=QuizResult.quiz_slug)
                .label("last_played_at"),
                func.row_number()
                .over(
                    partition_by=QuizResult.quiz_slug,
                    order_by=[
                        (QuizResult.score * 1.0 / QuizResult.total).desc(),
                        QuizResult.best_combo.desc(),
                    ],
                )
                .label("rank"),
            )
            .where(QuizResult.user_id == user_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(ranked).where(ranked.c.rank == 1).order_by(ranked.c.quiz_slug)
        )
        return [
            QuizBest(
                quiz=r.quiz_slug,
                best_score=r.score,
                total=r.total,
                best_combo=r.best_combo,
                plays=r.plays,
                last_played_at=r.last_played_at,
            )
            for r in rows
        ]

    async def district_exists(self, key: str) -> bool:
        result = await self.session.execute(select(Level.id).where(Level.district_key == key))
        return result.first() is not None
