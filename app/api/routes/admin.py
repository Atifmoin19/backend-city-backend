"""Admin API. Every route MUST depend on AdminUser or SuperAdminUser (server-side role check)."""

from fastapi import APIRouter

from app.core.deps import AdminUser
from app.schemas.auth import UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/whoami", response_model=UserPublic)
async def whoami(admin: AdminUser) -> UserPublic:
    """Placeholder admin route proving the role guard; real admin CRUD comes in Phase 1."""
    return UserPublic.model_validate(admin)
