from datetime import date

from pydantic import BaseModel


class DayCount(BaseModel):
    day: date
    count: int


class LearnerStats(BaseModel):
    total: int
    active_7d: int
    active_30d: int
    signups_14d: list[DayCount]  # oldest first, every day present (0 when none)


class FunnelRow(BaseModel):
    """How far learners got in one topic, in curriculum order."""

    topic: str
    title: str
    district: str
    briefed: int
    practiced: int  # passed at least one of the topic's practice games
    attempted: int | None  # submitted the checkpoint (None: no checkpoint)
    passed: int | None


class GameStats(BaseModel):
    slug: str
    title: str
    topic: str
    is_checkpoint: bool
    players: int
    attempts: int
    pass_rate: float  # 0-1: passed submissions (checkpoint) or passed players (practice)
    avg_score: float | None  # checkpoints only
    avg_hints: float | None  # checkpoints only


class QuizStats(BaseModel):
    quiz: str
    rounds: int
    players: int
    avg_pct: float


class AdminAnalytics(BaseModel):
    learners: LearnerStats
    funnel: list[FunnelRow]
    games: list[GameStats]  # hardest first (lowest pass rate)
    quizzes: list[QuizStats]
