import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models._columns import order_column, status_column
from app.models.enums import ContentStatus


class Level(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "levels"
    __table_args__ = (UniqueConstraint("track_id", "slug"),)

    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    district_key: Mapped[str] = mapped_column(String(40))
    story_intro: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = order_column()
    status: Mapped[ContentStatus] = status_column()
