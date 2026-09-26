import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Request, Response, status

from app.core.config import get_settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.deps import CurrentUser, SessionDep
from app.core.rate_limit import limiter
from app.db.session import SessionFactory
from app.schemas.auth import (
    AuthResponse,
    EmailTokenRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserPublic,
)
from app.services.account_service import AccountService
from app.services.auth_service import AuthService, IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])
_limit = get_settings().auth_rate_limit
_email_limit = get_settings().email_rate_limit
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _respond(response: Response, issued: IssuedSession) -> AuthResponse:
    set_auth_cookies(response, issued.access_token, issued.refresh_token)
    return AuthResponse(user=UserPublic.model_validate(issued.user))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_limit)
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    session: SessionDep,
    background: BackgroundTasks,
) -> AuthResponse:
    issued = await AuthService(session).register(body)
    background.add_task(_send_verification, issued.user.id)  # after the response: fast signup
    return _respond(response, issued)


async def _send_verification(user_id: uuid.UUID) -> None:
    async with SessionFactory() as session:
        user = await AccountService(session).users.get_by_id(user_id)
        if user is not None:
            await AccountService(session).send_verification(user)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(_limit)
async def login(
    request: Request, response: Response, body: LoginRequest, session: SessionDep
) -> AuthResponse:
    return _respond(response, await AuthService(session).login(body))


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit(_limit)
async def refresh(
    request: Request, response: Response, session: SessionDep, token: RefreshCookie = None
) -> AuthResponse:
    try:
        return _respond(response, await AuthService(session).refresh(token))
    except Exception:
        clear_auth_cookies(response)
        raise


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session: SessionDep, token: RefreshCookie = None) -> None:
    await AuthService(session).logout(token)
    clear_auth_cookies(response)


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@router.post("/verify-email", response_model=UserPublic)
async def verify_email(body: EmailTokenRequest, session: SessionDep) -> UserPublic:
    """Open the link from the verification email. 400 `invalid_token` if used or expired."""
    return UserPublic.model_validate(await AccountService(session).verify(body.token))


@router.post("/verify-email/resend", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_email_limit)
async def resend_verification(request: Request, user: CurrentUser, session: SessionDep) -> None:
    """Send a fresh verification link (older ones stop working)."""
    await AccountService(session).send_verification(user)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_email_limit)
async def forgot_password(
    request: Request, body: ForgotPasswordRequest, session: SessionDep
) -> None:
    """Email a reset link. Always 204, so nobody can probe which emails have accounts."""
    await AccountService(session).request_reset(body.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_limit)
async def reset_password(
    request: Request, response: Response, body: ResetPasswordRequest, session: SessionDep
) -> None:
    """Set a new password from a reset link and sign out every device."""
    await AccountService(session).reset(body.token, body.password)
    clear_auth_cookies(response)
