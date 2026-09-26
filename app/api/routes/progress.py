from fastapi import APIRouter, Request, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.core.rate_limit import limiter, user_or_ip
from app.schemas.auth import UserPublic
from app.schemas.feedback import FeedbackIn
from app.schemas.progress import ProgressImport, ProgressPublic, TopicProgressPublic
from app.schemas.quiz import PlacementIn, QuizResultIn, QuizResults
from app.schemas.stats import StatsPublic
from app.schemas.tracks import InterestList, TrackChoice
from app.services.feedback_service import FeedbackService
from app.services.progress_service import ProgressService
from app.services.quiz_service import QuizService
from app.services.stats_service import StatsService
from app.services.track_service import TrackService

router = APIRouter(prefix="/me", tags=["progress"])


@router.get("/progress", response_model=ProgressPublic)
async def get_progress(
    user: CurrentUser, session: SessionDep, track: str | None = None
) -> ProgressPublic:
    """Every published topic with the learner's state. `track` narrows it to one city."""
    return await ProgressService(session).progress(user, track)


@router.post("/progress/lessons/{topic_slug}", response_model=TopicProgressPublic)
async def complete_lesson(
    topic_slug: str, user: CurrentUser, session: SessionDep
) -> TopicProgressPublic:
    return await ProgressService(session).complete_lesson(user, topic_slug)


@router.post("/progress/import", response_model=ProgressPublic)
async def import_progress(
    body: ProgressImport, user: CurrentUser, session: SessionDep
) -> ProgressPublic:
    """One-time move of browser-kept progress (lessons + orientation, never checkpoints)."""
    return await ProgressService(session).import_local(user, body)


@router.post("/onboarded", status_code=status.HTTP_204_NO_CONTENT)
async def onboarded(user: CurrentUser, session: SessionDep) -> None:
    await ProgressService(session).mark_onboarded(user)


@router.put("/goal", response_model=UserPublic)
async def choose_goal(body: TrackChoice, user: CurrentUser, session: SessionDep) -> UserPublic:
    """Which side of the city the learner wants (signup question). A coming-soon choice is
    also recorded as interest."""
    return UserPublic.model_validate(await TrackService(session).choose_goal(user, body.track))


@router.get("/interests", response_model=InterestList)
async def interests(user: CurrentUser, session: SessionDep) -> InterestList:
    return await TrackService(session).interests(user)


@router.post("/interests", response_model=InterestList)
async def notify_me(body: TrackChoice, user: CurrentUser, session: SessionDep) -> InterestList:
    """ "Notify me" for a track that isn't open yet. Idempotent."""
    return await TrackService(session).notify_me(user, body.track)


@router.get("/quiz-results", response_model=QuizResults)
async def quiz_results(user: CurrentUser, session: SessionDep) -> QuizResults:
    """Best round per quiz (Speed Round, Pick the Line, placement)."""
    return await QuizService(session).results(user)


@router.post("/quiz-results", response_model=QuizResults, status_code=status.HTTP_201_CREATED)
async def record_quiz(body: QuizResultIn, user: CurrentUser, session: SessionDep) -> QuizResults:
    """Save a finished round. Quizzes are graded in the browser and never gate progress."""
    return await QuizService(session).record(user, body)


@router.put("/placement", response_model=UserPublic)
async def placement(body: PlacementIn, user: CurrentUser, session: SessionDep) -> UserPublic:
    """Where the placement quiz suggests starting. A suggestion only: nothing is unlocked."""
    return UserPublic.model_validate(await QuizService(session).set_placement(user, body))


@router.get("/stats", response_model=StatsPublic)
async def stats(user: CurrentUser, session: SessionDep, tz: str | None = None) -> StatsPublic:
    """XP, level, streak and badges, derived from the learner's history. `tz` (IANA name, e.g.
    Asia/Kolkata) sets where a day starts for streaks; unknown or missing means UTC."""
    return await StatsService(session).stats(user, tz)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(get_settings().feedback_rate_limit, key_func=user_or_ip)
async def send_feedback(
    request: Request, body: FeedbackIn, user: CurrentUser, session: SessionDep
) -> None:
    """A bug report, idea or content note for the team (admin inbox)."""
    await FeedbackService(session).send(user, body)
