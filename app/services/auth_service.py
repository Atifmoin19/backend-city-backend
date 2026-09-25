"""Auth business logic. Routers call this; it owns the transaction boundary."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


@dataclass(frozen=True)
class IssuedSession:
    user: User
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, data: RegisterRequest) -> IssuedSession:
        if await self.users.get_by_email(data.email):
            raise ConflictError("An account with this email already exists", code="email_taken")
        user = await self.users.add(
            User(
                email=data.email,
                password_hash=hash_password(data.password),
                display_name=data.display_name,
            )
        )
        issued = await self._issue(user)
        await self.session.commit()
        return issued

    async def login(self, data: LoginRequest) -> IssuedSession:
        user = await self.users.get_by_email(data.email)
        # Always run a hash verify so response time doesn't reveal whether the email exists
        valid = verify_password(data.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
        if not user or not valid:
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
        if user.is_blocked:
            raise ForbiddenError("This account is blocked", code="account_blocked")
        user.last_active_at = datetime.now(UTC)
        issued = await self._issue(user)
        await self.session.commit()
        return issued

    async def refresh(self, raw_refresh_token: str | None) -> IssuedSession:
        if not raw_refresh_token:
            raise UnauthorizedError("Missing refresh token", code="refresh_missing")
        now = datetime.now(UTC)
        stored = await self.refresh_tokens.get_by_hash(hash_token(raw_refresh_token))
        if stored is None:
            raise UnauthorizedError("Invalid refresh token", code="refresh_invalid")
        if stored.revoked_at is not None:
            # A rotated token was replayed: assume theft, kill every session for this user.
            await self.refresh_tokens.revoke_all_for_user(stored.user_id, now)
            await self.session.commit()
            raise UnauthorizedError("Refresh token reuse detected", code="refresh_reused")
        if stored.expires_at <= now:
            raise UnauthorizedError("Refresh token expired", code="refresh_expired")
        user = await self.users.get_by_id(stored.user_id)
        if user is None or user.is_blocked:
            raise UnauthorizedError("Session no longer valid", code="refresh_invalid")
        stored.revoked_at = now
        issued = await self._issue(user)
        await self.session.commit()
        return issued

    async def logout(self, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        stored = await self.refresh_tokens.get_by_hash(hash_token(raw_refresh_token))
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _issue(self, user: User) -> IssuedSession:
        raw = generate_opaque_token()
        ttl = timedelta(days=get_settings().refresh_token_ttl_days)
        await self.refresh_tokens.add(user.id, hash_token(raw), datetime.now(UTC) + ttl)
        return IssuedSession(user, create_access_token(user.id, user.role), raw)
