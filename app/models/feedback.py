import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class Feedback(UUIDPrimaryKey, CreatedAt, Base):
    """A learner's note to the team (bug, idea, content). Admins triage it in the inbox."""

    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # bug | idea | content | other
    message: Mapped[str] = mapped_column(Text)
    page: Mapped[str | None] = mapped_column(String(200))
    game_slug: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)  # new|seen|done
