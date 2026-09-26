"""Admin API. Every route MUST depend on AdminUser or SuperAdminUser (server-side role check)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, SessionDep, SuperAdminUser
from app.games.content import GameBody
from app.schemas.admin import (
    AdminContent,
    AdminGame,
    AdminUserDetail,
    AdminUserList,
    GameStatusUpdate,
    PublishRequest,
    TestRunRequest,
    TestRunResult,
    TopicSettingsUpdate,
    UserBlockUpdate,
    UserRoleUpdate,
)
from app.schemas.analytics import AdminAnalytics
from app.schemas.auth import UserPublic
from app.schemas.feedback import (
    AdminFeedback,
    AdminFeedbackList,
    FeedbackStatus,
    FeedbackStatusUpdate,
)
from app.services.admin_service import ContentAdminService, UserAdminService
from app.services.analytics_service import AnalyticsService
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/whoami", response_model=UserPublic)
async def whoami(admin: AdminUser) -> UserPublic:
    return UserPublic.model_validate(admin)


# --- content (content_editor or super_admin) ---


@router.get("/content", response_model=AdminContent)
async def content(_: AdminUser, session: SessionDep) -> AdminContent:
    """Levels -> topics (with settings) -> games (with current / newest version)."""
    return await ContentAdminService(session).content()


@router.patch("/topics/{slug}", response_model=AdminContent)
async def update_topic(
    slug: str, body: TopicSettingsUpdate, _: AdminUser, session: SessionDep
) -> AdminContent:
    return await ContentAdminService(session).update_topic(slug, body)


@router.get("/games/{slug}", response_model=AdminGame)
async def game(
    slug: str, _: AdminUser, session: SessionDep, version: Annotated[int | None, Query(ge=1)] = None
) -> AdminGame:
    """One version in full (server-only fields included). Default: the published one."""
    return await ContentAdminService(session).game(slug, version)


@router.post("/games/{slug}/versions", response_model=AdminGame, status_code=201)
async def save_version(
    slug: str, body: GameBody, admin: AdminUser, session: SessionDep
) -> AdminGame:
    """Save edits as a new draft version. Learners keep the current one until publish."""
    return await ContentAdminService(session).save_version(slug, body, admin)


@router.post("/games/{slug}/test-run", response_model=TestRunResult)
async def test_run(
    slug: str, body: TestRunRequest, _: AdminUser, session: SessionDep
) -> TestRunResult:
    """Run the reference solution (or a given snippet) on one variant, with every test shown."""
    return await ContentAdminService(session).test_run(slug, body.version, body.seed, body.snippet)


@router.post("/games/{slug}/publish", response_model=AdminGame)
async def publish(slug: str, body: PublishRequest, _: AdminUser, session: SessionDep) -> AdminGame:
    """Make a version live. Blocked unless its reference solution passes on fixed variants."""
    return await ContentAdminService(session).publish(slug, body.version)


@router.patch("/games/{slug}", response_model=AdminGame)
async def set_status(
    slug: str, body: GameStatusUpdate, _: AdminUser, session: SessionDep
) -> AdminGame:
    """Draft hides the game from learners; published shows it."""
    return await ContentAdminService(session).set_status(slug, body.status)


# --- users (list/detail: any admin; account actions: super_admin) ---


@router.get("/users", response_model=AdminUserList)
async def users(
    _: AdminUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserList:
    return await UserAdminService(session).list(q, limit, offset)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user(user_id: uuid.UUID, _: AdminUser, session: SessionDep) -> AdminUserDetail:
    return await UserAdminService(session).detail(user_id)


@router.post("/users/{user_id}/block", response_model=AdminUserDetail)
async def block(
    user_id: uuid.UUID, body: UserBlockUpdate, admin: SuperAdminUser, session: SessionDep
) -> AdminUserDetail:
    return await UserAdminService(session).set_blocked(user_id, body.blocked, admin)


@router.post("/users/{user_id}/role", response_model=AdminUserDetail)
async def role(
    user_id: uuid.UUID, body: UserRoleUpdate, admin: SuperAdminUser, session: SessionDep
) -> AdminUserDetail:
    return await UserAdminService(session).set_role(user_id, body.role, admin)


@router.post("/users/{user_id}/reset", response_model=AdminUserDetail)
async def reset(user_id: uuid.UUID, _: SuperAdminUser, session: SessionDep) -> AdminUserDetail:
    """Delete the learner's attempts and topic progress."""
    return await UserAdminService(session).reset_progress(user_id)


@router.get("/analytics", response_model=AdminAnalytics)
async def analytics(_: AdminUser, session: SessionDep) -> AdminAnalytics:
    """Learners, the per-topic drop-off funnel, hardest games and quiz stats."""
    return await AnalyticsService(session).overview()


@router.get("/feedback", response_model=AdminFeedbackList)
async def feedback_inbox(
    _: AdminUser, session: SessionDep, status: FeedbackStatus | None = None
) -> AdminFeedbackList:
    return await FeedbackService(session).inbox(status)


@router.patch("/feedback/{feedback_id}", response_model=AdminFeedback)
async def feedback_status(
    feedback_id: uuid.UUID, body: FeedbackStatusUpdate, _: AdminUser, session: SessionDep
) -> AdminFeedback:
    return await FeedbackService(session).set_status(feedback_id, body.status)
