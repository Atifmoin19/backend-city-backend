import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.enums import TopicProgressStatus
from app.models.game import Game, GameVersion
from app.models.progress import TopicProgress


class ProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- attempts ---

    async def latest_attempt(
        self, user_id: uuid.UUID, version_id: uuid.UUID, seed: int
    ) -> Attempt | None:
        """Most recent attempt on one variant (carries the hints used on it)."""
        result = await self.session.execute(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.game_version_id == version_id,
                Attempt.seed == seed,
            )
            .order_by(Attempt.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def practice_attempt(self, user_id: uuid.UUID, game_id: uuid.UUID) -> Attempt | None:
        """The one practice row kept per user and game (any version)."""
        result = await self.session.execute(
            select(Attempt)
            .join(GameVersion, GameVersion.id == Attempt.game_version_id)
            .where(
                Attempt.user_id == user_id,
                GameVersion.game_id == game_id,
                Attempt.is_checkpoint.is_(False),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def practice_passed_slugs(self, user_id: uuid.UUID) -> set[str]:
        result = await self.session.execute(
            select(Game.slug)
            .join(GameVersion, GameVersion.game_id == Game.id)
            .join(Attempt, Attempt.game_version_id == GameVersion.id)
            .where(
                Attempt.user_id == user_id,
                Attempt.is_checkpoint.is_(False),
                Attempt.passed.is_(True),
            )
            .distinct()
        )
        return set(result.scalars())

    async def graded_checkpoints(
        self, user_id: uuid.UUID, topic_id: uuid.UUID | None = None
    ) -> list[tuple[uuid.UUID, bool, datetime]]:
        """(topic_id, passed, created_at) of scored checkpoint attempts, newest first."""
        stmt = (
            select(Game.topic_id, Attempt.passed, Attempt.created_at)
            .join(GameVersion, GameVersion.id == Attempt.game_version_id)
            .join(Game, Game.id == GameVersion.game_id)
            .where(
                Attempt.user_id == user_id,
                Attempt.is_checkpoint.is_(True),
                Attempt.score.is_not(None),
            )
            .order_by(Attempt.created_at.desc())
        )
        if topic_id is not None:
            stmt = stmt.where(Game.topic_id == topic_id)
        return list(await self.session.execute(stmt))

    async def recent_attempts(
        self, user_id: uuid.UUID, limit: int = 50
    ) -> list[tuple[Attempt, str, int]]:
        """(attempt, game slug, version number), newest first."""
        stmt = (
            select(Attempt, Game.slug, GameVersion.version)
            .join(GameVersion, GameVersion.id == Attempt.game_version_id)
            .join(Game, Game.id == GameVersion.game_id)
            .where(Attempt.user_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
        return [(a, slug, v) for a, slug, v in await self.session.execute(stmt)]

    async def reset(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(Attempt).where(Attempt.user_id == user_id))
        await self.session.execute(delete(TopicProgress).where(TopicProgress.user_id == user_id))

    def add(self, row: Attempt | TopicProgress) -> None:
        self.session.add(row)

    # --- topic progress ---

    async def topic_progress(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> TopicProgress:
        """The user's row for a topic, created (not yet flushed) when missing."""
        row = await self.session.get(TopicProgress, (user_id, topic_id))
        if row is None:
            row = TopicProgress(
                user_id=user_id,
                topic_id=topic_id,
                status=TopicProgressStatus.UNLOCKED,
                best_score=0,
                stars=0,
                attempts_count=0,
            )
            self.session.add(row)
        return row

    async def all_topic_progress(self, user_id: uuid.UUID) -> dict[uuid.UUID, TopicProgress]:
        result = await self.session.execute(
            select(TopicProgress).where(TopicProgress.user_id == user_id)
        )
        return {row.topic_id: row for row in result.scalars()}
