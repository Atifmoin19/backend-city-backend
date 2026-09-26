"""Aggregate queries for the admin analytics page. Read-only."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, Float, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.attempt import Attempt
from app.models.chapter import Chapter
from app.models.enums import ContentStatus
from app.models.game import Game, GameVersion
from app.models.level import Level
from app.models.progress import TopicProgress
from app.models.quiz import QuizResult
from app.models.topic import Topic
from app.models.user import User


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def learner_counts(self, now: datetime) -> tuple[int, int, int]:
        week = func.count().filter(User.last_active_at >= now - timedelta(days=7))
        month = func.count().filter(User.last_active_at >= now - timedelta(days=30))
        row = (await self.session.execute(select(func.count(), week, month))).one()
        return int(row[0]), int(row[1]), int(row[2])

    async def signups_since(self, since: date) -> dict[date, int]:
        day = cast(User.created_at, Date)
        rows = await self.session.execute(
            select(day, func.count()).where(day >= since).group_by(day)
        )
        return {d: int(n) for d, n in rows}

    async def topics(self) -> list[tuple[Any, ...]]:
        """Published topics in curriculum order, with their district."""
        rows = await self.session.execute(
            select(Topic.id, Topic.slug, Topic.title, Level.district_key)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Level, Level.id == Chapter.level_id)
            .where(Topic.status == ContentStatus.PUBLISHED)
            .order_by(Level.order, Chapter.order, Topic.order)
        )
        return [tuple(r) for r in rows]

    async def briefed_and_passed(self) -> dict[object, tuple[int, int]]:
        rows = await self.session.execute(
            select(
                TopicProgress.topic_id,
                func.count().filter(TopicProgress.lesson_done_at.is_not(None)),
                func.count().filter(TopicProgress.passed_at.is_not(None)),
            ).group_by(TopicProgress.topic_id)
        )
        return {t: (int(b), int(p)) for t, b, p in rows}

    async def attempts_by_topic(self) -> dict[tuple[object, bool], int]:
        """Distinct learners per (topic, is_checkpoint): passed practice or scored checkpoint."""
        qualifies = (Attempt.is_checkpoint & Attempt.score.is_not(None)) | (
            ~Attempt.is_checkpoint & Attempt.passed
        )
        rows = await self.session.execute(
            select(Game.topic_id, Attempt.is_checkpoint, func.count(distinct(Attempt.user_id)))
            .join(GameVersion, GameVersion.id == Attempt.game_version_id)
            .join(Game, Game.id == GameVersion.game_id)
            .where(qualifies)
            .group_by(Game.topic_id, Attempt.is_checkpoint)
        )
        return {(t, bool(c)): int(n) for t, c, n in rows}

    async def games(self) -> list[tuple[Any, ...]]:
        current = GameVersion.id == Game.current_version_id
        versions = aliased(GameVersion)
        scored = Attempt.score.is_not(None)
        rows = await self.session.execute(
            select(
                Game.slug,
                GameVersion.title,
                Topic.slug,
                Game.is_checkpoint,
                func.count(distinct(Attempt.user_id)),
                func.count(Attempt.id).filter(scored | ~Attempt.is_checkpoint),
                func.count(Attempt.id).filter(Attempt.passed),
                func.count(distinct(Attempt.user_id)).filter(Attempt.passed),
                func.avg(Attempt.score).filter(scored),
                func.avg(cast(Attempt.hints_used, Float)).filter(scored),
            )
            .join(GameVersion, current)
            .join(Topic, Topic.id == Game.topic_id)
            .outerjoin(
                Attempt,
                # every version of the game counts, not only the live one
                Attempt.game_version_id.in_(
                    select(versions.id).where(versions.game_id == Game.id).correlate(Game)
                ),
            )
            .where(Game.status == ContentStatus.PUBLISHED)
            .group_by(Game.slug, GameVersion.title, Topic.slug, Game.is_checkpoint)
        )
        return [tuple(r) for r in rows]

    async def quizzes(self) -> list[tuple[Any, ...]]:
        rows = await self.session.execute(
            select(
                QuizResult.quiz_slug,
                func.count(),
                func.count(distinct(QuizResult.user_id)),
                func.avg(100.0 * QuizResult.score / QuizResult.total),
            )
            .group_by(QuizResult.quiz_slug)
            .order_by(func.count().desc())
        )
        return [tuple(r) for r in rows]
