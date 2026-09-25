import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class Attempt(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "attempts"
    # grading finds the open attempt for one variant (hint usage lives on it)
    __table_args__ = (Index("ix_attempts_user_version_seed", "user_id", "game_version_id", "seed"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    game_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_versions.id", ondelete="CASCADE"), index=True
    )
    seed: Mapped[int]  # regenerates the exact variant + hidden tests for grading
    code: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None]  # percent; null while a checkpoint is started but unsubmitted
    passed: Mapped[bool] = mapped_column(default=False)
    hints_used: Mapped[int] = mapped_column(default=0)
    duration_seconds: Mapped[int | None]
    is_checkpoint: Mapped[bool] = mapped_column(default=False)
