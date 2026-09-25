import hmac

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.errors import error_body
from app.core.security import decode_access_token

CLIENT_IP_HEADER = "x-bc-client-ip"
PROXY_SECRET_HEADER = "x-bc-proxy-secret"  # noqa: S105 — a header name, not a secret


def client_ip(request: Request) -> str:
    """The learner's IP: from our own proxy when it proves itself, else the socket peer."""
    secret = get_settings().proxy_shared_secret
    key = secret.get_secret_value() if secret else ""  # empty env var = not configured
    sent = request.headers.get(PROXY_SECRET_HEADER, "")
    forwarded = request.headers.get(CLIENT_IP_HEADER)
    trusted = bool(key and sent) and hmac.compare_digest(sent.encode(), key.encode())
    if trusted and forwarded:
        return forwarded.strip()[:64]
    return get_remote_address(request)


def user_or_ip(request: Request) -> str:
    """Signed-in learners get their own bucket (grading); visitors are keyed by IP."""
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    return f"user:{payload['sub']}" if payload else f"ip:{client_ip(request)}"


# In-memory storage: fine for one Render instance. Move to Redis storage if we scale out.
limiter = Limiter(key_func=client_ip, enabled=get_settings().rate_limit_enabled)


async def _rate_limited(_: Request, exc: Exception) -> JSONResponse:
    detail = exc.detail if isinstance(exc, RateLimitExceeded) else "rate limit exceeded"
    return JSONResponse(
        error_body("rate_limited", f"Too many requests: {detail}"),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def register_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limited)
