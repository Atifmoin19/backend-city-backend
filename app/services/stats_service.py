"""Loads a learner's records and hands them to the reward rules (app/services/rewards.py)."""

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.game import Game, GameVersion
from app.models.progress import TopicProgress
from app.models.quiz import QuizResult
from app.models.topic import Topic
from app.models.user import User
from app.schemas.stats import BadgePublic, LevelPublic, StatsPublic, StreakPublic
from app.services import rewards


def zone(tz: str | None) -> ZoneInfo:
    """The learner's timezone for day boundaries; UTC when missing or unknown."""
    try:
        return ZoneInfo(tz) if tz else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def records(self, user: User) -> rewards.Records:
        attempts = await self.session.execute(
            select(
                Game.slug, Attempt.passed, Attempt.score, Attempt.is_checkpoint, Attempt.created_at
            )
            .join(GameVersion, GameVersion.id == Attempt.game_version_id)
            .join(Game, Game.id == GameVersion.game_id)
            .where(Attempt.user_id == user.id)
        )
        practice: list[rewards.PracticeRec] = []
        checkpoints: list[rewards.CheckpointRec] = []
        for slug, passed, score, is_checkpoint, at in attempts:
            if not is_checkpoint:
                practice.append(rewards.PracticeRec(slug, passed, at))
            elif score is not None:  # a checkpoint only counts once it was submitted
                checkpoints.append(rewards.CheckpointRec(slug, score, at))
        has_checkpoint = (
            select(Game.id)
            .where(Game.topic_id == Topic.id, Game.is_checkpoint)
            .exists()
            .label("has_checkpoint")
        )
        topics = await self.session.execute(
            select(
                Topic.slug,
                TopicProgress.lesson_done_at,
                TopicProgress.passed_at,
                TopicProgress.stars,
                has_checkpoint,
            )
            .join(Topic, Topic.id == TopicProgress.topic_id)
            .where(TopicProgress.user_id == user.id)
        )
        quizzes = await self.session.execute(
            select(
                QuizResult.quiz_slug,
                QuizResult.score,
                QuizResult.total,
                QuizResult.best_combo,
                QuizResult.created_at,
            ).where(QuizResult.user_id == user.id)
        )
        return rewards.Records(
            practice=practice,
            checkpoints=checkpoints,
            topics=[rewards.TopicRec(*row) for row in topics],
            quizzes=[rewards.QuizRec(*row) for row in quizzes],
        )

    async def stats(self, user: User, tz: str | None, now: datetime | None = None) -> StatsPublic:
        z = zone(tz)
        r = await self.records(user)
        xp = rewards.xp_total(r)
        today = (now or datetime.now(z)).astimezone(z).date()
        return StatsPublic(
            xp=xp,
            level=LevelPublic(**asdict(rewards.level_for(xp))),
            streak=StreakPublic(**asdict(rewards.streak(rewards.activity_days(r, z), today))),
            badges=[BadgePublic(**asdict(b)) for b in rewards.badges(r, z)],
        )
