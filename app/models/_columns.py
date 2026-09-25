"""Reusable column factories shared by content models."""

from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ContentStatus


def status_column() -> Mapped[ContentStatus]:
    return mapped_column(
        Enum(ContentStatus, name="content_status", values_callable=lambda e: [m.value for m in e]),
        default=ContentStatus.DRAFT,
    )


def order_column() -> Mapped[int]:
    return mapped_column("order", default=0)
