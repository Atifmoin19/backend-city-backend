from typing import Literal

from pydantic import BaseModel, Field

TrackStatus = Literal["open", "coming_soon"]


class TrackPublic(BaseModel):
    slug: str
    title: str
    description: str
    status: TrackStatus


class TrackChoice(BaseModel):
    track: str = Field(min_length=1, max_length=80)


class InterestList(BaseModel):
    tracks: list[str]  # slugs the learner asked to be notified about
