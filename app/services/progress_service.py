"""Learner progress: lessons, practice passes, checkpoint results, retest cooldown.

A topic is complete when its checkpoint is passed, or, for a lesson-only topic (no
published checkpoint game), when its briefing is finished.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, TooManyRequestsError
from app.games.content import GameContent
from app.models.attempt import Attempt
from app.models.enums import ContentStatus, TopicProgressStatus
from app.models.game import Game
from app.models.progress import TopicProgress
from app.models.topic import Topic
from app.models.user import User
from app.repositories.content_repository import ContentRepository
from app.repositories.progress_repository import ProgressRepository
from app.schemas.progress import (
    CheckpointProgress,
    ProgressImport,
    ProgressPublic,
    TopicProgressPublic,
)

PASSED = TopicProgressStatus.PASSED


def _now() -> datetime:
    return datetime.now(UTC)


def _published(games: Sequence[Game]) -> list[Game]:
    return [g for g in games if g.status == ContentStatus.PUBLISHED]


def _fails_and_retry(
    history: list[tuple[bool, datetime]], cooldown_minutes: int
) -> tuple[int, datetime | None]:
    """Consecutive fails since the last pass (newest first) and when a retest opens."""
    fails = 0
    for passed, _ in history:
        if passed:
            break
        fails += 1
    retry_at = None
    if fails and cooldown_minutes > 0:
        opens = history[0][1] + timedelta(minutes=cooldown_minutes)
        retry_at = opens if opens > _now() else None
    return fails, retry_at


class ProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProgressRepository(session)
        self.content = ContentRepository(session)

    # --- reads ---

    async def progress(self, user: User, track: str | None = None) -> ProgressPublic:
        rows = await self.repo.all_topic_progress(user.id)
        practice = await self.repo.practice_passed_slugs(user.id)
        history: dict[uuid.UUID, list[tuple[bool, datetime]]] = {}
        for topic_id, passed, at in await self.repo.graded_checkpoints(user.id):
            history.setdefault(topic_id, []).append((passed, at))
        topics = [
            self._topic_view(
                topic, track_slug, games, rows.get(topic.id), practice, history.get(topic.id, [])
            )
            for topic, track_slug, games in await self.content.topics_with_games(track)
            if topic.status == ContentStatus.PUBLISHED
        ]
        return ProgressPublic(onboarded=user.onboarded_at is not None, topics=topics)

    async def topic(self, user: User, topic: Topic) -> TopicProgressPublic:
        track, games = await self._placement(topic)
        row = await self.repo.all_topic_progress(user.id)
        history = [(p, at) for _, p, at in await self.repo.graded_checkpoints(user.id, topic.id)]
        practice = await self.repo.practice_passed_slugs(user.id)
        return self._topic_view(topic, track, games, row.get(topic.id), practice, history)

    async def _placement(self, topic: Topic) -> tuple[str, list[Game]]:
        for t, track, games in await self.content.topics_with_games():
            if t.id == topic.id:
                return track, games
        raise NotFoundError(f"Topic {topic.slug!r} not found", code="topic_not_found")

    def _topic_view(
        self,
        topic: Topic,
        track: str,
        games: Sequence[Game],
        row: TopicProgress | None,
        practice: set[str],
        history: list[tuple[bool, datetime]],
    ) -> TopicProgressPublic:
        live = _published(games)
        practice_games = [g.slug for g in live if not g.is_checkpoint]
        checkpoint_game = next((g.slug for g in live if g.is_checkpoint), None)
        lesson_done = row is not None and row.lesson_done_at is not None
        checkpoint_passed = row is not None and row.passed_at is not None
        complete = checkpoint_passed if checkpoint_game else lesson_done
        fails, retry_at = _fails_and_retry(history, topic.retest_cooldown_minutes)
        checkpoint = None
        if row is not None and row.attempts_count > 0:
            checkpoint = CheckpointProgress(
                best_score=row.best_score,
                stars=row.stars,
                attempts=row.attempts_count,
                passed=checkpoint_passed,
                passed_at=row.passed_at,
            )
        if complete:
            status = PASSED
        elif row is not None:
            status = TopicProgressStatus.UNLOCKED
        else:
            status = TopicProgressStatus.LOCKED
        return TopicProgressPublic(
            topic=topic.slug,
            track=track,
            status=status,
            complete=complete,
            lesson_done=lesson_done,
            practice_games=practice_games,
            checkpoint_game=checkpoint_game,
            practice_passed=[s for s in practice_games if s in practice],
            checkpoint=checkpoint,
            consecutive_fails=fails,
            retry_at=retry_at,
        )

    async def _topic_or_404(self, slug: str) -> Topic:
        topic = await self.content.topic_by_slug(slug)
        if topic is None or topic.status != ContentStatus.PUBLISHED:
            raise NotFoundError(f"Topic {slug!r} not found", code="topic_not_found")
        return topic

    # --- writes ---

    async def complete_lesson(self, user: User, topic_slug: str) -> TopicProgressPublic:
        topic = await self._topic_or_404(topic_slug)
        await self._mark_lesson(user, topic)
        await self.session.commit()
        return await self.topic(user, topic)

    async def _mark_lesson(self, user: User, topic: Topic) -> None:
        row = await self.repo.topic_progress(user.id, topic.id)
        if row.lesson_done_at is None:
            row.lesson_done_at = _now()
        _, games = await self._placement(topic)
        if not any(g.is_checkpoint for g in _published(games)):
            row.status = PASSED  # lesson-only topic: the briefing is the whole topic
            row.passed_at = row.passed_at or _now()

    async def record_practice(
        self, user: User, game: GameContent, seed: int, passed: bool, score: int
    ) -> TopicProgressPublic:
        """Practice runs in the browser, so the result is self-reported and low stakes:
        one row per user and game, and a pass is never taken back."""
        attempt = await self.repo.practice_attempt(user.id, game.game_id)
        if attempt is None:
            attempt = Attempt(
                user_id=user.id,
                game_version_id=game.version_id,
                seed=seed,
                is_checkpoint=False,
                passed=passed,
                score=score,
                hints_used=0,
            )
            self.repo.add(attempt)
        else:
            attempt.game_version_id, attempt.seed = game.version_id, seed
            attempt.passed = attempt.passed or passed
            attempt.score = max(attempt.score or 0, score)
        await self.repo.topic_progress(user.id, game.topic_id)
        await self.session.commit()
        topic = await self.session.get(Topic, game.topic_id)
        if topic is None:
            raise NotFoundError("Topic not found", code="topic_not_found")
        return await self.topic(user, topic)

    async def hints_used(self, user: User, game: GameContent, seed: int) -> int:
        attempt = await self.repo.latest_attempt(user.id, game.version_id, seed)
        return attempt.hints_used if attempt else 0

    async def record_hint(self, user: User, game: GameContent, seed: int, tier: int) -> None:
        """Checkpoint hints are counted on the open attempt for this variant."""
        attempt = await self.repo.latest_attempt(user.id, game.version_id, seed)
        if attempt is None or attempt.score is not None:
            carried = attempt.hints_used if attempt else 0
            attempt = Attempt(
                user_id=user.id,
                game_version_id=game.version_id,
                seed=seed,
                is_checkpoint=True,
                passed=False,
                hints_used=carried,
            )
            self.repo.add(attempt)
        attempt.hints_used = max(attempt.hints_used, tier)
        await self.session.commit()

    async def ensure_can_retest(self, user: User, game: GameContent) -> None:
        history = [
            (p, at) for _, p, at in await self.repo.graded_checkpoints(user.id, game.topic_id)
        ]
        _, retry_at = _fails_and_retry(history, game.retest_cooldown_minutes)
        if retry_at is not None:
            minutes = max(1, round((retry_at - _now()).total_seconds() / 60))
            raise TooManyRequestsError(
                f"Take a short break: the next checkpoint attempt opens in {minutes} min",
                code="retest_cooldown",
            )

    async def record_checkpoint(
        self,
        user: User,
        game: GameContent,
        seed: int,
        code: str,
        score: int,
        passed: bool,
        stars: int,
        hints_used: int,
    ) -> datetime | None:
        """Save a scored checkpoint attempt; returns when a retest opens (cooldown) if any."""
        attempt = await self.repo.latest_attempt(user.id, game.version_id, seed)
        if attempt is None or attempt.score is not None:
            attempt = Attempt(
                user_id=user.id,
                game_version_id=game.version_id,
                seed=seed,
                is_checkpoint=True,
                hints_used=hints_used,
            )
            self.repo.add(attempt)
        attempt.code, attempt.score, attempt.passed = code, score, passed

        row = await self.repo.topic_progress(user.id, game.topic_id)
        row.attempts_count += 1
        row.best_score = max(row.best_score, score)
        row.stars = max(row.stars, stars)
        if passed:
            row.status = PASSED
            row.passed_at = row.passed_at or _now()
        await self.session.commit()
        if passed or game.retest_cooldown_minutes <= 0:
            return None
        return _now() + timedelta(minutes=game.retest_cooldown_minutes)

    async def mark_onboarded(self, user: User) -> None:
        if user.onboarded_at is None:
            user.onboarded_at = _now()
            await self.session.commit()

    async def import_local(self, user: User, body: ProgressImport) -> ProgressPublic:
        if body.onboarded and user.onboarded_at is None:
            user.onboarded_at = _now()
        for slug in dict.fromkeys(body.lessons_done):
            topic = await self.content.topic_by_slug(slug)
            if topic is not None and topic.status == ContentStatus.PUBLISHED:
                await self._mark_lesson(user, topic)
        await self.session.commit()
        return await self.progress(user)
