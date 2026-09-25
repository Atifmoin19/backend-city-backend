from fastapi import Response

from app.core.config import get_settings

ACCESS_COOKIE = "bc_access"
REFRESH_COOKIE = "bc_refresh"


def _set(response: Response, key: str, value: str, *, max_age: int, path: str) -> None:
    s = get_settings()
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        path=path,
        domain=s.cookie_domain,
        secure=s.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    s = get_settings()
    _set(response, ACCESS_COOKIE, access_token, max_age=s.access_token_ttl_minutes * 60, path="/")
    _set(
        response,
        REFRESH_COOKIE,
        refresh_token,
        max_age=s.refresh_token_ttl_days * 86400,
        path=s.refresh_cookie_path,
    )


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=s.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path=s.refresh_cookie_path, domain=s.cookie_domain)
