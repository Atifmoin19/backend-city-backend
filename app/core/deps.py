"""Shared FastAPI dependencies: DB session, current user, role guards."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.enums import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    payload = decode_access_token(access_token) if access_token else None
    if payload is None:
        raise UnauthorizedError("Not authenticated", code="not_authenticated")
    user = await UserRepository(session).get_by_id(uuid.UUID(payload["sub"]))
    if user is None or user.is_blocked:
        raise UnauthorizedError("Not authenticated", code="not_authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: Role) -> Callable[[User], Awaitable[User]]:
    """Role guard. Always checks the DB role, never trusts the role claim in the JWT alone."""

    async def guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Insufficient permissions", code="forbidden_role")
        return user

    return guard


AdminUser = Annotated[User, Depends(require_role(Role.CONTENT_EDITOR, Role.SUPER_ADMIN))]
SuperAdminUser = Annotated[User, Depends(require_role(Role.SUPER_ADMIN))]
