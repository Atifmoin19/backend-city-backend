"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from app.models.attempt import Attempt
from app.models.chapter import Chapter
from app.models.game import Game, GameVersion
from app.models.interest import TrackInterest
from app.models.level import Level
from app.models.progress import TopicProgress
from app.models.tokens import EmailToken, RefreshToken
from app.models.topic import Topic
from app.models.track import Track
from app.models.user import User

__all__ = [
    "Attempt",
    "Chapter",
    "EmailToken",
    "Game",
    "GameVersion",
    "Level",
    "RefreshToken",
    "Topic",
    "TopicProgress",
    "Track",
    "TrackInterest",
    "User",
]
