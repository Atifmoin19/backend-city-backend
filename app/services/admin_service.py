"""Admin MVP (ideology §10.5): content versions + test-run + publish, topic settings, users.

Content versions are immutable. Saving creates a new draft version; learners keep playing
the current one until an admin publishes the draft, and attempts started on an older
version are graded against it (ideology §10.1).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.games.catalog import body_columns, body_of
from app.games.content import GameBody
from app.games.validate import content_issues
from app.games.variants import new_seed, pick_params, render
from app.models.game import Game, GameVersion
from app.models.topic import Topic
from app.models.user import User
from app.repositories.content_repository import ContentRepository
from app.repositories.progress_repository import ProgressRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminAttempt,
    AdminContent,
    AdminGame,
    AdminGameSummary,
    AdminLevel,
    AdminTopic,
    AdminUserDetail,
    AdminUserList,
    AdminUserRow,
    AdminVersionSummary,
    TestRunCase,
    TestRunResult,
    TopicSettingsUpdate,
)
from app.services.grading_service import run_cases
from app.services.progress_service import ProgressService

PUBLISH_SEEDS = (1, 2, 3)  # publishing re-runs the test on these variants, server side


class ContentAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ContentRepository(session)

    async def content(self) -> AdminContent:
        latest = await self.repo.latest_versions()
        numbers = await self.repo.version_numbers_by_id()
        games = {t.id: g for t, _, g in await self.repo.topics_with_games()}
        levels: dict[uuid.UUID, AdminLevel] = {}
        for level, topic in await self.repo.levels_with_topics():
            entry = levels.setdefault(
                level.id,
                AdminLevel(
                    slug=level.slug, title=level.title, district_key=level.district_key, topics=[]
                ),
            )
            entry.topics.append(
                AdminTopic(
                    slug=topic.slug,
                    title=topic.title,
                    status=topic.status,
                    pass_threshold=topic.pass_threshold,
                    hints_allowed=topic.hints_allowed,
                    retest_cooldown_minutes=topic.retest_cooldown_minutes,
                    games=[
                        AdminGameSummary(
                            slug=g.slug,
                            title=await self._title(g),
                            game_type=g.game_type,
                            is_checkpoint=g.is_checkpoint,
                            status=g.status,
                            current_version=numbers.get(g.current_version_id)
                            if g.current_version_id
                            else None,
                            latest_version=latest.get(g.id, 0),
                        )
                        for g in games.get(topic.id, [])
                    ],
                )
            )
        return AdminContent(levels=list(levels.values()))

    async def _title(self, game: Game) -> str:
        if game.current_version_id is None:
            return game.slug
        v = await self.session.get(GameVersion, game.current_version_id)
        return v.title if v else game.slug

    async def _game(self, slug: str) -> Game:
        game = await self.repo.game_by_slug(slug)
        if game is None:
            raise NotFoundError(f"Game {slug!r} not found", code="game_not_found")
        return game

    async def _version(self, game: Game, number: int) -> GameVersion:
        version = await self.repo.version_by_number(game.id, number)
        if version is None:
            raise NotFoundError(f"Version {number} not found", code="version_not_found")
        return version

    async def game(self, slug: str, number: int | None = None) -> AdminGame:
        game = await self._game(slug)
        history = await self.repo.version_history(game.id)
        if not history:
            raise NotFoundError(f"Game {slug!r} has no versions", code="version_not_found")
        if number is None:  # default: what learners play, else the newest
            version = next((v for v, _ in history if v.id == game.current_version_id), None)
            version = version or history[0][0]
        else:
            version = await self._version(game, number)
        topic = await self.session.get(Topic, game.topic_id)
        placement = await self.repo.game_version(version.id)
        assert topic is not None and placement is not None  # noqa: S101 — FK guarantees
        return AdminGame(
            slug=game.slug,
            topic=topic.slug,
            district=placement[3].district_key,
            game_type=game.game_type,
            is_checkpoint=game.is_checkpoint,
            status=game.status,
            pass_threshold=topic.pass_threshold,
            version=version.version,
            is_current=version.id == game.current_version_id,
            body=body_of(version),
            versions=[
                AdminVersionSummary(
                    version=v.version,
                    created_at=v.created_at,
                    created_by=email,
                    is_current=v.id == game.current_version_id,
                )
                for v, email in history
            ],
        )

    async def save_version(self, slug: str, body: GameBody, admin: User) -> AdminGame:
        game = await self._game(slug)
        issues = content_issues(body, is_checkpoint=game.is_checkpoint)
        if issues:
            raise AppError("; ".join(issues), code="invalid_game")
        number = await self.repo.next_version_number(game.id)
        self.session.add(
            GameVersion(game_id=game.id, version=number, created_by=admin.id, **body_columns(body))
        )
        await self.session.commit()
        return await self.game(slug, number)

    async def test_run(
        self, slug: str, number: int, seed: int | None, snippet: str | None
    ) -> TestRunResult:
        game = await self._game(slug)
        body = body_of(await self._version(game, number))
        topic = await self.session.get(Topic, game.topic_id)
        threshold = topic.pass_threshold if topic else 70
        issues = content_issues(body, is_checkpoint=game.is_checkpoint)
        seed = seed or new_seed()
        variant = pick_params(body, seed)
        reference = snippet is None
        code = render(body.reference_solution, variant.params) if reference else str(snippet)

        run = await run_cases(body, variant, code)
        score = _score(run.results)
        tests = [(t, False) for t in run.public] + [(t, True) for t in run.hidden]
        results: list[dict[str, Any] | None] = list(run.results) or [None] * len(tests)
        cases = [
            TestRunCase(
                name=t["name"],
                hidden=hidden,
                request=t["request"],
                expect_status=t["expect_status"],
                expect_body=t.get("expect_body"),
                status=r["status"] if r else None,
                passed=bool(r and r["passed"]),
            )
            for (t, hidden), r in zip(tests, results, strict=True)
        ]
        starter = await run_cases(body, variant, _starter_region(body, variant.params))
        starter_score = _score(starter.results) if starter.verdict == "graded" else None
        if reference and (run.verdict != "graded" or score < 100):
            issues.append(f"reference solution scores {score}% (needs 100%)")
        if starter_score is not None and starter_score >= threshold:
            issues.append(f"untouched starter code already scores {starter_score}%")
        return TestRunResult(
            version=number,
            seed=seed,
            params=variant.params,
            verdict=run.verdict,
            score=score,
            passed=score >= threshold,
            error=run.error,
            violations=[f"line {v.line}: {v.message}" for v in run.violations],
            cases=cases,
            starter_score=starter_score,
            issues=issues,
        )

    async def publish(self, slug: str, number: int) -> AdminGame:
        """Make a version the one learners play, after re-checking it on fixed variants."""
        game = await self._game(slug)
        version = await self._version(game, number)
        for seed in PUBLISH_SEEDS:
            result = await self.test_run(slug, number, seed, None)
            if result.issues:
                raise AppError(
                    f"Can't publish v{number} (variant seed {seed}): " + "; ".join(result.issues),
                    code="publish_blocked",
                )
        game.current_version_id = version.id
        await self.session.commit()
        return await self.game(slug, number)

    async def set_status(self, slug: str, status: str) -> AdminGame:
        game = await self._game(slug)
        game.status = status  # type: ignore[assignment]  # validated by the schema enum
        await self.session.commit()
        return await self.game(slug)

    async def update_topic(self, slug: str, patch: TopicSettingsUpdate) -> AdminContent:
        topic = await self.repo.topic_by_slug(slug)
        if topic is None:
            raise NotFoundError(f"Topic {slug!r} not found", code="topic_not_found")
        for field, value in patch.model_dump(exclude_none=True).items():
            setattr(topic, field, value)
        await self.session.commit()
        return await self.content()


def _score(results: list[dict[str, object]]) -> int:
    return round(100 * sum(1 for r in results if r["passed"]) / len(results)) if results else 0


def _starter_region(body: GameBody, params: dict[str, object]) -> str:
    """The editable lines exactly as learners first see them."""
    lines = render(body.starter_code, params).splitlines()
    marks = [ln.strip() for ln in lines]
    start = marks.index(body.editable_region["start_marker"])
    end = marks.index(body.editable_region["end_marker"])
    return "\n".join(lines[start + 1 : end])


class UserAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def list(self, q: str | None, limit: int, offset: int) -> AdminUserList:
        users = await self.users.search(q, limit, offset)
        stats = await self.users.learning_stats([u.id for u in users])
        return AdminUserList(
            total=await self.users.count(q),
            users=[self._row(u, stats.get(u.id, (0, 0))) for u in users],
        )

    @staticmethod
    def _row(user: User, stats: tuple[int, int]) -> AdminUserRow:
        row = AdminUserRow.model_validate(user)
        row.topics_passed, row.checkpoint_attempts = stats
        return row

    async def _user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found", code="user_not_found")
        return user

    async def detail(self, user_id: uuid.UUID) -> AdminUserDetail:
        user = await self._user(user_id)
        stats = await self.users.learning_stats([user.id])
        attempts = await ProgressRepository(self.session).recent_attempts(user.id)
        return AdminUserDetail(
            user=self._row(user, stats[user.id]),
            progress=await ProgressService(self.session).progress(user),
            attempts=[
                AdminAttempt(
                    game=slug,
                    version=version,
                    is_checkpoint=a.is_checkpoint,
                    score=a.score,
                    passed=a.passed,
                    hints_used=a.hints_used,
                    created_at=a.created_at,
                )
                for a, slug, version in attempts
            ],
        )

    async def set_blocked(self, user_id: uuid.UUID, blocked: bool, admin: User) -> AdminUserDetail:
        user = await self._user(user_id)
        if user.id == admin.id:
            raise ForbiddenError("You can't block your own account", code="self_action")
        user.is_blocked = blocked
        await self.session.commit()
        return await self.detail(user_id)

    async def set_role(self, user_id: uuid.UUID, role: str, admin: User) -> AdminUserDetail:
        user = await self._user(user_id)
        if user.id == admin.id:
            raise ForbiddenError("You can't change your own role", code="self_action")
        user.role = role  # type: ignore[assignment]  # validated by the schema enum
        await self.session.commit()
        return await self.detail(user_id)

    async def reset_progress(self, user_id: uuid.UUID) -> AdminUserDetail:
        await self._user(user_id)
        await ProgressRepository(self.session).reset(user_id)
        await self.session.commit()
        return await self.detail(user_id)
