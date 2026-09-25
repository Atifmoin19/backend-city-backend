from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.core.config import get_settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.deps import CurrentUser, SessionDep
from app.core.rate_limit import limiter
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from app.services.auth_service import AuthService, IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])
_limit = get_settings().auth_rate_limit
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _respond(response: Response, issued: IssuedSession) -> AuthResponse:
    set_auth_cookies(response, issued.access_token, issued.refresh_token)
    return AuthResponse(user=UserPublic.model_validate(issued.user))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_limit)
async def register(
    request: Request, response: Response, body: RegisterRequest, session: SessionDep
) -> AuthResponse:
    return _respond(response, await AuthService(session).register(body))


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
