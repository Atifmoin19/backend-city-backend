"""Admin payloads. These MAY contain server-only content (hidden tests, reference solutions):
every route using them depends on AdminUser."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.games.content import GameBody
from app.models.enums import ContentStatus, Role
from app.schemas.progress import ProgressPublic


class AdminGameSummary(BaseModel):
    slug: str
    title: str
    game_type: str
    is_checkpoint: bool
    status: ContentStatus
    current_version: int | None  # what learners play
    latest_version: int  # newest saved (a draft when above current)


class AdminTopic(BaseModel):
    slug: str
    title: str
    status: ContentStatus
    pass_threshold: int
    hints_allowed: bool
    retest_cooldown_minutes: int
    games: list[AdminGameSummary]


class AdminLevel(BaseModel):
    slug: str
    title: str
    district_key: str
    topics: list[AdminTopic]


class AdminContent(BaseModel):
    levels: list[AdminLevel]


class AdminVersionSummary(BaseModel):
    version: int
    created_at: datetime
    created_by: str | None  # admin email; None = seeded from content/seed
    is_current: bool


class AdminGame(BaseModel):
    slug: str
    topic: str
    district: str
    game_type: str
    is_checkpoint: bool
    status: ContentStatus
    pass_threshold: int
    version: int  # the version `body` belongs to
    is_current: bool
    body: GameBody
    versions: list[AdminVersionSummary]


class GameStatusUpdate(BaseModel):
    status: ContentStatus


class PublishRequest(BaseModel):
    version: int = Field(ge=1)


class TestRunRequest(BaseModel):
    version: int = Field(ge=1)
    seed: int | None = Field(default=None, ge=1, le=2**31 - 1)
    # Run this instead of the reference solution (e.g. to check a wrong answer fails)
    snippet: str | None = Field(default=None, max_length=20_000)


class TestRunCase(BaseModel):
    name: str
    hidden: bool
    request: dict[str, Any]
    expect_status: int
    expect_body: Any = None
    status: int | None
    passed: bool


class TestRunResult(BaseModel):
    version: int
    seed: int
    params: dict[str, Any]
    verdict: str
    score: int
    passed: bool
    error: str | None
    violations: list[str]
    cases: list[TestRunCase]
    starter_score: int | None  # the untouched starter must NOT pass
    issues: list[str]  # problems that block publishing


class TopicSettingsUpdate(BaseModel):
    pass_threshold: int | None = Field(default=None, ge=1, le=100)
    hints_allowed: bool | None = None
    retest_cooldown_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class AdminUserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    is_blocked: bool
    created_at: datetime
    last_active_at: datetime | None
    topics_passed: int = 0
    checkpoint_attempts: int = 0


class AdminUserList(BaseModel):
    total: int
    users: list[AdminUserRow]


class AdminAttempt(BaseModel):
    game: str
    version: int
    is_checkpoint: bool
    score: int | None
    passed: bool
    hints_used: int
    created_at: datetime


class AdminUserDetail(BaseModel):
    user: AdminUserRow
    progress: ProgressPublic
    attempts: list[AdminAttempt]


class UserBlockUpdate(BaseModel):
    blocked: bool


class UserRoleUpdate(BaseModel):
    role: Role
