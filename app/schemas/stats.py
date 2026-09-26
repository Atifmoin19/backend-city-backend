from datetime import datetime

from pydantic import BaseModel


class LevelPublic(BaseModel):
    level: int
    xp_into: int
    xp_needed: int


class StreakPublic(BaseModel):
    current: int
    best: int
    active_today: bool


class BadgePublic(BaseModel):
    key: str
    title: str
    description: str
    earned_at: datetime | None


class StatsPublic(BaseModel):
    xp: int
    level: LevelPublic
    streak: StreakPublic
    badges: list[BadgePublic]
