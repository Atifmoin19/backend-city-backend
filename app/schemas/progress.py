"""Learner progress payloads (GET /me/progress and the calls that change it)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TopicProgressStatus


class CheckpointProgress(BaseModel):
    best_score: int
    stars: int
    attempts: int
    passed: bool
    passed_at: datetime | None


class TopicGame(BaseModel):
    """A live game in a topic, as learners see it listed (no answers, no tests)."""

    slug: str
    title: str
    objective: str
    is_checkpoint: bool


class TopicProgressPublic(BaseModel):
    topic: str  # topic slug
    track: str  # track ("city") slug, e.g. python-backend
    status: TopicProgressStatus
    complete: bool
    lesson_done: bool
    practice_games: list[str]  # published practice game slugs, in play order
    checkpoint_game: str | None
    games: list[TopicGame] = []  # live games in play order (titles for the district page)
    practice_passed: list[str]
    checkpoint: CheckpointProgress | None
    consecutive_fails: int  # checkpoint fails since the last pass (soft-fail help after 2)
    retry_at: datetime | None  # set while a retest cooldown is running


class ProgressPublic(BaseModel):
    onboarded: bool
    topics: list[TopicProgressPublic]


class PracticeRequest(BaseModel):
    attempt_token: str = Field(min_length=10, max_length=2000)
    passed: bool
    score: int = Field(ge=0, le=100)


class ProgressImport(BaseModel):
    """One-time move of progress kept in the browser before the progress API existed.

    Checkpoint results are not accepted: they only count when graded on the server.
    """

    onboarded: bool = False
    lessons_done: list[str] = Field(default=[], max_length=100)
