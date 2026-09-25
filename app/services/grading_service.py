"""Checkpoint grading: regenerate the variant from the signed seed, run public + hidden tests
in the sandbox, and score by behavior (status codes), never by string-matching code."""

from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_attempt_token
from app.games.registry import template_for
from app.games.variants import pick_params, render, render_json
from app.sandbox.executor import SandboxLimits, execute
from app.sandbox.policy import check_snippet
from app.schemas.games import GradeResponse, TestOutcome, Violation
from app.services.game_service import require_game
from harness.splice import SpliceError, splice


def stars_for(score: int, passed: bool, hints_used: int = 0) -> int:
    if not passed:
        return 0
    if score >= 95 and hints_used == 0:
        return 3
    return 2 if score >= 85 else 1


async def grade(slug: str, attempt_token: str, snippet: str) -> GradeResponse:
    settings = get_settings()
    decoded = decode_attempt_token(attempt_token)
    if decoded is None or decoded[0] != slug:
        raise AppError("Attempt token invalid or expired", code="attempt_invalid")
    game = require_game(slug)
    variant = pick_params(game, decoded[1])
    threshold = game.pass_threshold

    violations = check_snippet(snippet, max_chars=settings.sandbox_max_snippet_chars)
    if violations:
        return GradeResponse(
            verdict="rejected",
            score=0,
            passed=False,
            stars=0,
            pass_threshold=threshold,
            violations=[Violation(line=v.line, message=v.message) for v in violations],
        )

    public: list[dict[str, Any]] = render_json(game.public_tests, variant.params)
    hidden = template_for(game.game_type).hidden_tests(game, variant)
    try:
        source = splice(render(game.starter_code, variant.params), snippet, game.editable_region)
    except SpliceError as exc:
        raise AppError(str(exc), code="splice_failed") from exc

    result = await execute(
        source,
        public + hidden,
        SandboxLimits(settings.sandbox_timeout_seconds, settings.sandbox_memory_limit_mb),
    )
    base = {"score": 0, "passed": False, "stars": 0, "pass_threshold": threshold}
    if result.timed_out:
        return GradeResponse(verdict="timeout", error="Your code took too long to run", **base)
    if result.report is None:
        return GradeResponse(
            verdict="crashed", error="The sandbox crashed running your code", **base
        )
    if not result.report["ok"]:
        return GradeResponse(verdict="load_error", error=result.report["error"], **base)

    outcomes = result.report["results"]
    pub, hid = outcomes[: len(public)], outcomes[len(public) :]
    total_passed = sum(1 for o in outcomes if o["passed"])
    score = round(100 * total_passed / len(outcomes)) if outcomes else 0
    passed = score >= threshold
    return GradeResponse(
        verdict="graded",
        score=score,
        passed=passed,
        stars=stars_for(score, passed),
        pass_threshold=threshold,
        public_results=[TestOutcome.model_validate(o) for o in pub],
        hidden_passed=sum(1 for o in hid if o["passed"]),
        hidden_total=len(hid),
    )
