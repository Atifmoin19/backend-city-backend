import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class QuizResult(UUIDPrimaryKey, CreatedAt, Base):
    """One finished quiz round (Speed Round, Pick the Line, placement). Quiz content lives in
    the frontend like lesson checks; this keeps scores for bests, XP and analytics."""

    __tablename__ = "quiz_results"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    quiz_slug: Mapped[str] = mapped_column(String(80), index=True)
    score: Mapped[int]
    total: Mapped[int]
    best_combo: Mapped[int] = mapped_column(default=0)
    seconds: Mapped[int | None]
