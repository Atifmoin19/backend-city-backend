from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_body

# In-memory storage: fine for one Render instance. Move to Redis storage if we scale out.
limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)


async def _rate_limited(_: Request, exc: Exception) -> JSONResponse:
    detail = exc.detail if isinstance(exc, RateLimitExceeded) else "rate limit exceeded"
    return JSONResponse(
        error_body("rate_limited", f"Too many requests: {detail}"),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def register_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limited)
