"""Email verification and password reset. Tokens are single-use, stored hashed, and expire."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import generate_opaque_token, hash_password, hash_token
from app.models.enums import EmailTokenPurpose
from app.models.tokens import EmailToken
from app.models.user import User
from app.repositories.email_token_repository import EmailTokenRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.mailer import send_email


class InvalidTokenError(AppError):
    status_code = 400

    def __init__(self) -> None:
        super().__init__("This link is invalid or has expired", code="invalid_token")


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = EmailTokenRepository(session)

    async def _new_token(self, user: User, purpose: EmailTokenPurpose, ttl: timedelta) -> str:
        now = datetime.now(UTC)
        await self.tokens.use_all(user.id, purpose, now)
        raw = generate_opaque_token()
        self.tokens.add(
            EmailToken(
                user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=now + ttl
            )
        )
        await self.session.commit()
        return raw

    async def _take(self, raw: str, purpose: EmailTokenPurpose) -> User:
        token = await self.tokens.get_by_hash(hash_token(raw))
        now = datetime.now(UTC)
        if (
            token is None
            or token.purpose != purpose
            or token.used_at is not None
            or token.expires_at <= now
        ):
            raise InvalidTokenError()
        user = await self.users.get_by_id(token.user_id)
        if user is None or user.is_blocked:
            raise InvalidTokenError()
        token.used_at = now
        return user

    async def send_verification(self, user: User) -> None:
        if user.is_verified:
            return
        s = get_settings()
        raw = await self._new_token(
            user, EmailTokenPurpose.VERIFY, timedelta(hours=s.verify_token_ttl_hours)
        )
        link = f"{s.app_url.rstrip('/')}/verify-email?token={raw}"
        await send_email("verify", user.email, user.display_name, link)

    async def verify(self, raw: str) -> User:
        user = await self._take(raw, EmailTokenPurpose.VERIFY)
        user.is_verified = True
        await self.session.commit()
        return user

    async def request_reset(self, email: str) -> None:
        """Always succeeds from the caller's view, so it can't tell which emails exist."""
        user = await self.users.get_by_email(email)
        if user is None or user.is_blocked:
            return
        s = get_settings()
        raw = await self._new_token(
            user, EmailTokenPurpose.RESET, timedelta(minutes=s.reset_token_ttl_minutes)
        )
        link = f"{s.app_url.rstrip('/')}/reset-password?token={raw}"
        await send_email("reset", user.email, user.display_name, link)

    async def reset(self, raw: str, password: str) -> None:
        user = await self._take(raw, EmailTokenPurpose.RESET)
        now = datetime.now(UTC)
        user.password_hash = hash_password(password)
        # the reset link proves the inbox, and every old session is signed out
        user.is_verified = True
        await RefreshTokenRepository(self.session).revoke_all_for_user(user.id, now)
        await self.session.commit()
