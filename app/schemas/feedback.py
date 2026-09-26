import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FeedbackKind = Literal["bug", "idea", "content", "other"]
FeedbackStatus = Literal["new", "seen", "done"]


class FeedbackIn(BaseModel):
    kind: FeedbackKind
    message: str = Field(min_length=3, max_length=2000)
    page: str | None = Field(default=None, max_length=200)
    game_slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")


class AdminFeedback(BaseModel):
    id: uuid.UUID
    kind: FeedbackKind
    message: str
    page: str | None
    game_slug: str | None
    status: FeedbackStatus
    created_at: datetime
    user_id: uuid.UUID | None
    user_email: str | None
    user_name: str | None


class AdminFeedbackList(BaseModel):
    items: list[AdminFeedback]
    counts: dict[str, int]  # per status, for the inbox tabs


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
