from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Keep-alive target for cron pings. Must stay cheap: no DB call."""
    return HealthResponse(status="ok")
