import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TopicProgressStatus


class TopicProgress(Base):
    __tablename__ = "topic_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[TopicProgressStatus] = mapped_column(
        Enum(
            TopicProgressStatus,
            name="topic_progress_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TopicProgressStatus.LOCKED,
    )
    best_score: Mapped[int] = mapped_column(default=0)
    stars: Mapped[int] = mapped_column(default=0)
    attempts_count: Mapped[int] = mapped_column(default=0)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lesson_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
