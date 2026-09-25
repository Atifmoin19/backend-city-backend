from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models.enums import Role


class User(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64))
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=Role.USER,
    )
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_blocked: Mapped[bool] = mapped_column(default=False)
    experience_level: Mapped[str | None] = mapped_column(String(32))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Track slug the learner chose at signup ("Which side of the city?")
    learning_goal: Mapped[str | None] = mapped_column(String(80))
