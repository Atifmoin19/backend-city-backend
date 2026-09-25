import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import register_rate_limiting
from app.sandbox.executor import WarmUnavailableError, warm_sandbox

log = logging.getLogger(__name__)


async def _warm_sandbox() -> None:
    try:
        await warm_sandbox.warm_up()
    except WarmUnavailableError as exc:
        log.warning("warm sandbox did not start (%s); grades will use cold runs", exc)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # In the background: a slow CPU must not delay the health check / first request
    task = asyncio.create_task(_warm_sandbox()) if get_settings().sandbox_warm else None
    yield
    if task is not None:
        task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    register_rate_limiting(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
