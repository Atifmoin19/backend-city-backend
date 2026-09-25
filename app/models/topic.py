import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models._columns import order_column, status_column
from app.models.enums import ContentStatus


class Topic(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chapter_id", "slug"),)

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    order: Mapped[int] = order_column()
    status: Mapped[ContentStatus] = status_column()
    pass_threshold: Mapped[int] = mapped_column(default=70)  # percent
    required_games_count: Mapped[int] = mapped_column(default=3)
    hints_allowed: Mapped[bool] = mapped_column(default=True)
    retest_cooldown_minutes: Mapped[int] = mapped_column(default=0)
