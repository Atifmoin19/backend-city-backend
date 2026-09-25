"""Checkpoint grading: regenerate the variant from the signed seed, run public + hidden tests
in the sandbox, and score by behavior (status codes), never by string-matching code."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.games.content import GameBody
from app.games.registry import generator_for
from app.games.variants import Variant, pick_params, render, render_json
from app.models.user import User
from app.sandbox.executor import SandboxLimits, execute
from app.sandbox.policy import check_snippet
from app.schemas.games import GradeResponse, TestOutcome, Violation
from app.services.game_service import game_for_token
from app.services.progress_service import ProgressService
from harness.splice import SpliceError, splice

SCORED_VERDICTS = frozenset({"graded", "load_error", "timeout"})  # count as an attempt


def stars_for(score: int, passed: bool, hints_used: int = 0) -> int:
    if not passed:
        return 0
    if score >= 95 and hints_used == 0:
        return 3
    return 2 if score >= 85 else 1


async def grade(
    session: AsyncSession, slug: str, attempt_token: str, snippet: str, user: User
) -> GradeResponse:
    game, claims = await game_for_token(session, slug, attempt_token)
    if claims.mode != "checkpoint" or not game.is_checkpoint:
        raise AppError("Only checkpoint attempts are graded", code="attempt_invalid")
    progress = ProgressService(session)
    await progress.ensure_can_retest(user, game)
    hints_used = await progress.hints_used(user, game, claims.seed)

    result = await run_checks(
        game, pick_params(game, claims.seed), snippet, game.pass_threshold, hints_used
    )
    if result.verdict in SCORED_VERDICTS:
        result.retry_at = await progress.record_checkpoint(
            user,
            game,
            claims.seed,
            snippet,
            score=result.score,
            passed=result.passed,
            stars=result.stars,
            hints_used=hints_used,
        )
    return result


@dataclass(frozen=True)
class CaseRun:
    """One sandbox run of a snippet against a variant's public + hidden tests."""

    verdict: str  # graded | rejected | load_error | timeout | crashed
    public: list[dict[str, Any]]
    hidden: list[dict[str, Any]]
    results: list[dict[str, Any]] = field(default_factory=list)  # public then hidden
    error: str | None = None
    violations: list[Violation] = field(default_factory=list)


async def run_cases(game: GameBody, variant: Variant, snippet: str) -> CaseRun:
    """Policy check + sandbox run. No scoring rules, no persistence (admin test-runs too)."""
    settings = get_settings()
    public: list[dict[str, Any]] = render_json(game.public_tests, variant.params)
    hidden = generator_for(game).hidden_tests(game, variant)
    violations = check_snippet(snippet, max_chars=settings.sandbox_max_snippet_chars)
    if violations:
        return CaseRun(
            "rejected",
            public,
            hidden,
            violations=[Violation(line=v.line, message=v.message) for v in violations],
        )
    try:
        source = splice(render(game.starter_code, variant.params), snippet, game.editable_region)
    except SpliceError as exc:
        raise AppError(str(exc), code="splice_failed") from exc
    result = await execute(
        source,
        public + hidden,
        SandboxLimits(
            settings.sandbox_timeout_seconds,
            settings.sandbox_memory_limit_mb,
            settings.sandbox_startup_seconds,
        ),
    )
    if result.timed_out:
        return CaseRun("timeout", public, hidden, error="Your code took too long to run")
    if result.report is None:
        return CaseRun("crashed", public, hidden, error="The sandbox crashed running your code")
    if not result.report["ok"]:
        return CaseRun("load_error", public, hidden, error=result.report["error"])
    return CaseRun("graded", public, hidden, results=result.report["results"])


async def run_checks(
    game: GameBody, variant: Variant, snippet: str, threshold: int, hints_used: int = 0
) -> GradeResponse:
    """Run + score a checkpoint submission (hint penalty and stars included)."""
    run = await run_cases(game, variant, snippet)
    base: dict[str, Any] = {
        "score": 0,
        "passed": False,
        "stars": 0,
        "pass_threshold": threshold,
        "hints_used": hints_used,
    }
    if run.verdict != "graded":
        return GradeResponse(
            verdict=run.verdict, error=run.error, violations=run.violations, **base
        )
    outcomes = run.results
    pub, hid = outcomes[: len(run.public)], outcomes[len(run.public) :]
    total_passed = sum(1 for o in outcomes if o["passed"])
    raw = round(100 * total_passed / len(outcomes)) if outcomes else 0
    penalty = min(raw, hints_used * get_settings().hint_penalty_per_tier)
    score = raw - penalty
    passed = score >= threshold
    return GradeResponse(
        verdict="graded",
        score=score,
        raw_score=raw,
        hint_penalty=penalty,
        passed=passed,
        stars=stars_for(score, passed, hints_used),
        pass_threshold=threshold,
        hints_used=hints_used,
        public_results=[TestOutcome.model_validate(o) for o in pub],
        hidden_passed=sum(1 for o in hid if o["passed"]),
        hidden_total=len(hid),
    )
