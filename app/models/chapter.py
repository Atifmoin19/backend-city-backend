import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models._columns import order_column, status_column
from app.models.enums import ContentStatus


class Chapter(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("level_id", "slug"),)

    level_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("levels.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    order: Mapped[int] = order_column()
    status: Mapped[ContentStatus] = status_column()
