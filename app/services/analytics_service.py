"""Admin analytics: who is learning, where they drop off, which games are hardest."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    AdminAnalytics,
    DayCount,
    FunnelRow,
    GameStats,
    LearnerStats,
    QuizStats,
)


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AnalyticsRepository(session)

    async def overview(self, now: datetime | None = None) -> AdminAnalytics:
        now = now or datetime.now(UTC)
        games = await self._games()
        return AdminAnalytics(
            learners=await self._learners(now),
            funnel=await self._funnel({g.topic for g in games if g.is_checkpoint}),
            games=games,
            quizzes=[
                QuizStats(quiz=q, rounds=r, players=p, avg_pct=round(float(a or 0), 1))
                for q, r, p, a in await self.repo.quizzes()
            ],
        )

    async def _learners(self, now: datetime) -> LearnerStats:
        total, week, month = await self.repo.learner_counts(now)
        first = (now - timedelta(days=13)).date()
        per_day = await self.repo.signups_since(first)
        days = [first + timedelta(days=i) for i in range(14)]
        return LearnerStats(
            total=total,
            active_7d=week,
            active_30d=month,
            signups_14d=[DayCount(day=d, count=per_day.get(d, 0)) for d in days],
        )

    async def _funnel(self, checkpoint_topics: set[str]) -> list[FunnelRow]:
        progress = await self.repo.briefed_and_passed()
        attempts = await self.repo.attempts_by_topic()
        rows = []
        for topic_id, slug, title, district in await self.repo.topics():
            briefed, passed = progress.get(topic_id, (0, 0))
            has_cp = str(slug) in checkpoint_topics
            rows.append(
                FunnelRow(
                    topic=str(slug),
                    title=str(title),
                    district=str(district),
                    briefed=briefed,
                    practiced=attempts.get((topic_id, False), 0),
                    # lesson-only topics "pass" on the briefing: no checkpoint columns
                    attempted=attempts.get((topic_id, True), 0) if has_cp else None,
                    passed=passed if has_cp else None,
                )
            )
        return rows

    async def _games(self) -> list[GameStats]:
        out = []
        for (
            slug,
            title,
            topic,
            is_cp,
            players,
            attempts,
            passed,
            passed_players,
            score,
            hints,
        ) in await self.repo.games():
            if is_cp:
                rate = passed / attempts if attempts else 0.0
            else:
                rate = passed_players / players if players else 0.0
            out.append(
                GameStats(
                    slug=str(slug),
                    title=str(title),
                    topic=str(topic),
                    is_checkpoint=bool(is_cp),
                    players=int(players),
                    attempts=int(attempts),
                    pass_rate=round(rate, 3),
                    avg_score=round(float(score), 1) if is_cp and score is not None else None,
                    avg_hints=round(float(hints), 2) if is_cp and hints is not None else None,
                )
            )
        # hardest first; games nobody played yet go last
        return sorted(out, key=lambda g: (g.players == 0, g.pass_rate, g.slug))
