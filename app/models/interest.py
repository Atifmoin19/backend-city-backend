import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt


class TrackInterest(CreatedAt, Base):
    """A learner asked to be told when a (coming soon) track opens."""

    __tablename__ = "track_interests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True, index=True
    )
