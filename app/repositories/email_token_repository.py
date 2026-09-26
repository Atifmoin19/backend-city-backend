import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EmailTokenPurpose
from app.models.tokens import EmailToken


class EmailTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, token: EmailToken) -> None:
        self.session.add(token)

    async def get_by_hash(self, token_hash: str) -> EmailToken | None:
        result = await self.session.execute(
            select(EmailToken).where(EmailToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def use_all(self, user_id: uuid.UUID, purpose: EmailTokenPurpose, at: datetime) -> None:
        """Retire every open token of this kind (a new link replaces older ones)."""
        await self.session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user_id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=at)
        )
