from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import rewards
from tests.conftest import register
from tests.test_progress import submit

T0 = datetime(2026, 9, 1, 10, tzinfo=UTC)
UTC_Z = ZoneInfo("UTC")


def recs(**kw: object) -> rewards.Records:
    base: dict[str, object] = {"practice": [], "checkpoints": [], "topics": [], "quizzes": []}
    base.update(kw)
    return rewards.Records(**base)  # type: ignore[arg-type]


def test_xp_counts_each_thing_once_and_caps_quiz_grinding() -> None:
    r = recs(
        practice=[
            rewards.PracticeRec("signal-codes", True, T0),
            rewards.PracticeRec("method-lanes", False, T0),
        ],
        topics=[rewards.TopicRec("how-requests-travel", T0, T0, 2)],
        quizzes=[
            rewards.QuizRec("status-speed-round", 10, 14, 4, T0 + timedelta(minutes=i))
            for i in range(5)
        ],
    )
    # lesson 20 + practice 30 + checkpoint 100 + 2 stars 50 + 3 counted rounds x 10 right x 2
    assert rewards.xp_total(r) == 20 + 30 + 150 + 60


def test_levels_get_longer() -> None:
    assert rewards.level_for(0) == rewards.Level(1, 0, 100)
    assert rewards.level_for(99).level == 1
    assert rewards.level_for(100) == rewards.Level(2, 0, 150)
    assert rewards.level_for(260) == rewards.Level(3, 10, 200)


def test_streak_survives_until_a_whole_day_is_missed() -> None:
    days = [date(2026, 9, d) for d in (1, 2, 3, 5, 6)]
    assert rewards.streak(days, date(2026, 9, 6)) == rewards.Streak(2, 3, True)
    assert rewards.streak(days, date(2026, 9, 7)) == rewards.Streak(2, 3, False)
    assert rewards.streak(days, date(2026, 9, 8)).current == 0
    assert rewards.streak([], date(2026, 9, 8)) == rewards.Streak(0, 0, False)


def test_days_follow_the_learners_timezone() -> None:
    late = datetime(2026, 9, 1, 20, tzinfo=UTC)  # already 2 September in Kolkata
    r = recs(quizzes=[rewards.QuizRec("x", 1, 1, 0, late)])
    assert rewards.activity_days(r, UTC_Z) == [date(2026, 9, 1)]
    assert rewards.activity_days(r, ZoneInfo("Asia/Kolkata")) == [date(2026, 9, 2)]


def test_badges_carry_when_they_were_earned() -> None:
    r = recs(
        practice=[
            rewards.PracticeRec("front-desk", True, T0),
            rewards.PracticeRec("score-board", True, T0 + timedelta(days=1)),
        ],
        quizzes=[
            rewards.QuizRec("status-speed-round", 9, 14, 6, T0 + timedelta(days=2)),
            rewards.QuizRec("pick-the-line-gate", 5, 5, 5, T0 + timedelta(days=2)),
        ],
    )
    earned = {b.key: b.earned_at for b in rewards.badges(r, UTC_Z)}
    assert earned["first-200"] == T0
    assert earned["warmed-up"] == T0 + timedelta(days=1)
    assert earned["combo-5"] == earned["sharp-eye"] == T0 + timedelta(days=2)
    assert earned["streak-3"] == datetime(2026, 9, 3, tzinfo=UTC_Z)
    assert earned["cleared"] is None and earned["streak-7"] is None


async def test_stats_endpoint(client: AsyncClient) -> None:
    assert (await client.get("/me/stats")).status_code == 401
    await register(client)
    await client.post("/me/progress/lessons/python-for-js")
    await client.post(
        "/me/quiz-results",
        json={"quiz": "status-speed-round", "score": 8, "total": 14, "best_combo": 5},
    )
    res = await client.get("/me/stats", params={"tz": "Asia/Kolkata"})
    assert res.status_code == 200
    body = res.json()
    assert body["xp"] == 20 + 16
    assert body["level"] == {"level": 1, "xp_into": 36, "xp_needed": 100}
    assert body["streak"] == {"current": 1, "best": 1, "active_today": True}
    earned = {b["key"] for b in body["badges"] if b["earned_at"]}
    assert earned == {"combo-5"}
    # an unknown timezone falls back to UTC instead of failing
    assert (await client.get("/me/stats", params={"tz": "Mars/Olympus"})).status_code == 200


def test_a_lesson_only_topic_is_not_a_checkpoint_pass() -> None:
    r = recs(topics=[rewards.TopicRec("python-for-js", T0, T0, 0, has_checkpoint=False)])
    assert rewards.xp_total(r) == rewards.XP_LESSON
    assert {b.key for b in rewards.badges(r, UTC_Z) if b.earned_at} == set()


async def test_stats_count_real_practice_and_checkpoints(
    client: AsyncClient, db: AsyncSession
) -> None:
    await register(client)
    variant = (await client.get("/games/badge-check/variant", params={"seed": 3})).json()
    await client.post(
        "/games/badge-check/practice",
        json={"attempt_token": variant["attempt_token"], "passed": True, "score": 100},
    )
    await submit(client, db, 12, correct=True)  # signup-gate checkpoint, no hints: 3 stars
    body = (await client.get("/me/stats")).json()
    assert body["xp"] == rewards.XP_PRACTICE + rewards.XP_CHECKPOINT + 3 * rewards.XP_PER_STAR
    earned = {b["key"] for b in body["badges"] if b["earned_at"]}
    assert {"first-200", "cleared", "no-hint-hero"} <= earned
