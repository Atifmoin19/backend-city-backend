"""XP, levels, streaks and badges, derived from what the learner already did (ideology 6.4).

Pure functions over plain records, so the rules are easy to test and existing learners get
credit for their history. Nothing here is stored; `StatsService` loads the records.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

XP_LESSON = 20
XP_PRACTICE = 30
XP_CHECKPOINT = 100
XP_PER_STAR = 25
XP_PER_QUIZ_ANSWER = 2
QUIZ_ROUNDS_PER_DAY = 3  # per quiz; later rounds still count for streaks, not XP
DAILY_QUIZ = "daily"  # the daily challenge: one scored round per day, plus a bonus
XP_DAILY_BONUS = 20


@dataclass(frozen=True)
class PracticeRec:
    game: str
    passed: bool
    at: datetime


@dataclass(frozen=True)
class CheckpointRec:
    game: str
    score: int
    at: datetime


@dataclass(frozen=True)
class TopicRec:
    topic: str
    lesson_done_at: datetime | None
    passed_at: datetime | None
    stars: int
    has_checkpoint: bool = True  # lesson-only topics (the Academy) "pass" on the briefing

    @property
    def cleared_at(self) -> datetime | None:
        """When the checkpoint was passed; None for lesson-only topics."""
        return self.passed_at if self.has_checkpoint else None


@dataclass(frozen=True)
class QuizRec:
    quiz: str
    score: int
    total: int
    best_combo: int
    at: datetime


@dataclass(frozen=True)
class Records:
    practice: list[PracticeRec]
    checkpoints: list[CheckpointRec]
    topics: list[TopicRec]
    quizzes: list[QuizRec]


@dataclass(frozen=True)
class Level:
    level: int
    xp_into: int  # XP earned inside the current level
    xp_needed: int  # XP the current level takes in total


@dataclass(frozen=True)
class Streak:
    current: int
    best: int
    active_today: bool


@dataclass(frozen=True)
class Badge:
    key: str
    title: str
    description: str
    earned_at: datetime | None


def xp_total(r: Records) -> int:
    xp = XP_LESSON * sum(1 for t in r.topics if t.lesson_done_at)
    xp += XP_PRACTICE * len({p.game for p in r.practice if p.passed})
    xp += sum(XP_CHECKPOINT + XP_PER_STAR * t.stars for t in r.topics if t.cleared_at)
    rounds: dict[tuple[str, date], int] = defaultdict(int)
    for q in sorted(r.quizzes, key=lambda q: q.at):
        key = (q.quiz, q.at.date())
        rounds[key] += 1
        if q.quiz == DAILY_QUIZ:
            if rounds[key] == 1:
                xp += XP_DAILY_BONUS + XP_PER_QUIZ_ANSWER * q.score
        elif rounds[key] <= QUIZ_ROUNDS_PER_DAY:
            xp += XP_PER_QUIZ_ANSWER * q.score
    return xp


def level_for(xp: int) -> Level:
    """Level 1 takes 100 XP, each next level 50 more (100, 150, 200, ...)."""
    level, need = 1, 100
    while xp >= need:
        xp -= need
        level += 1
        need += 50
    return Level(level=level, xp_into=xp, xp_needed=need)


def activity_days(r: Records, tz: ZoneInfo) -> list[date]:
    stamps = [p.at for p in r.practice] + [c.at for c in r.checkpoints] + [q.at for q in r.quizzes]
    stamps += [t.lesson_done_at for t in r.topics if t.lesson_done_at]
    return sorted({s.astimezone(tz).date() for s in stamps})


def streak(days: list[date], today: date) -> Streak:
    best = run = 0
    prev: date | None = None
    for d in days:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    # the streak is still alive until a whole day is missed
    alive = prev is not None and today - prev <= timedelta(days=1)
    return Streak(current=run if alive else 0, best=best, active_today=prev == today)


def _streak_reached(days: list[date], length: int, tz: ZoneInfo) -> datetime | None:
    run = 0
    prev: date | None = None
    for d in days:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        prev = d
        if run >= length:
            return datetime(d.year, d.month, d.day, tzinfo=tz)
    return None


def _first(stamps: list[datetime]) -> datetime | None:
    return min(stamps) if stamps else None


def _nth(stamps: list[datetime], n: int) -> datetime | None:
    return sorted(stamps)[n - 1] if len(stamps) >= n else None


def _daily_firsts(r: Records, tz: ZoneInfo) -> list[datetime]:
    """The first daily-challenge round of each local day, oldest first."""
    firsts: dict[date, datetime] = {}
    for q in sorted(r.quizzes, key=lambda q: q.at):
        if q.quiz == DAILY_QUIZ:
            firsts.setdefault(q.at.astimezone(tz).date(), q.at)
    return list(firsts.values())


def badges(r: Records, tz: ZoneInfo) -> list[Badge]:
    days = activity_days(r, tz)
    passed_practice = {p.game: p.at for p in r.practice if p.passed}
    warmups = [passed_practice.get(g) for g in ("front-desk", "score-board")]
    speed = [q.at for q in r.quizzes if q.quiz == "status-speed-round" and q.best_combo >= 5]
    sharp = [q.at for q in r.quizzes if q.quiz.startswith("pick-the-line") and q.score == q.total]
    return [
        Badge(
            "first-200",
            "First 200 OK",
            "Pass your first practice game.",
            _first(list(passed_practice.values())),
        ),
        Badge(
            "briefed",
            "Well briefed",
            "Finish three briefings.",
            _nth([t.lesson_done_at for t in r.topics if t.lesson_done_at], 3),
        ),
        Badge(
            "warmed-up",
            "Warmed up",
            "Clear both Academy warm-ups.",
            max(w for w in warmups if w) if all(warmups) else None,
        ),
        Badge(
            "cleared",
            "Lights on",
            "Pass your first checkpoint.",
            _first([t.cleared_at for t in r.topics if t.cleared_at]),
        ),
        Badge(
            "no-hint-hero",
            "No-Hint Hero",
            "Earn three stars on a checkpoint.",
            _first([t.cleared_at for t in r.topics if t.cleared_at and t.stars == 3]),
        ),
        Badge(
            "three-districts",
            "Night shift regular",
            "Pass three checkpoints.",
            _nth([t.cleared_at for t in r.topics if t.cleared_at], 3),
        ),
        Badge(
            "combo-5",
            "Combo x5",
            "Five right in a row in the Status Code Speed Round.",
            _first(speed),
        ),
        Badge("sharp-eye", "Sharp eye", "A perfect Pick the Line round.", _first(sharp)),
        Badge(
            "daily-5",
            "Daily regular",
            "Finish the daily challenge on five different days.",
            _nth(_daily_firsts(r, tz), 5),
        ),
        Badge(
            "found-start",
            "Found your start",
            "Take the placement check.",
            _first([q.at for q in r.quizzes if q.quiz == "placement"]),
        ),
        Badge(
            "streak-3",
            "Three-day streak",
            "Practise three days in a row.",
            _streak_reached(days, 3, tz),
        ),
        Badge(
            "streak-7",
            "Week on the clock",
            "Practise seven days in a row.",
            _streak_reached(days, 7, tz),
        ),
    ]
