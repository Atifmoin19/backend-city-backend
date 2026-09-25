from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models._columns import order_column, status_column
from app.models.enums import ContentStatus


class Track(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "tracks"

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = order_column()
    status: Mapped[ContentStatus] = status_column()
