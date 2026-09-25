import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models._columns import order_column, status_column
from app.models.enums import ContentStatus

Json = dict[str, Any]


class Game(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "games"

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    game_type: Mapped[str] = mapped_column(String(40))
    is_checkpoint: Mapped[bool] = mapped_column(default=False)
    order: Mapped[int] = order_column()
    status: Mapped[ContentStatus] = status_column()
    # use_alter breaks the games <-> game_versions FK cycle
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("game_versions.id", use_alter=True, ondelete="SET NULL")
    )


class GameVersion(UUIDPrimaryKey, CreatedAt, Base):
    """Immutable snapshot. Editing a live game creates a new version (ideology §10.1).

    SECURITY: hidden_test_template and reference_solution must never be serialized
    into any learner-facing schema.
    """

    __tablename__ = "game_versions"
    __table_args__ = (UniqueConstraint("game_id", "version"),)

    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    title: Mapped[str] = mapped_column(String(120), default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    rules: Mapped[list[str]] = mapped_column(JSONB, default=list)
    scenario: Mapped[Json] = mapped_column(JSONB, default=dict)
    starter_code: Mapped[str] = mapped_column(Text)
    editable_region: Mapped[Json] = mapped_column(JSONB, default=dict)
    public_tests: Mapped[list[Json]] = mapped_column(JSONB, default=list)
    hidden_test_template: Mapped[Json] = mapped_column(JSONB, default=dict)
    variant_params: Mapped[Json] = mapped_column(JSONB, default=dict)
    reference_solution: Mapped[str] = mapped_column(Text, default="")
    visualizer_type: Mapped[str] = mapped_column(String(40))
    character_key: Mapped[str] = mapped_column(String(40))
    hints: Mapped[list[Json]] = mapped_column(JSONB, default=list)
    dialogue: Mapped[Json] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
