"""Load a game's full source (starter + snippet) and run request tests against its `app`."""

import traceback
from types import ModuleType
from typing import Any, TypedDict

from harness.asgi import SimRequest, SimResponse, call


class TestCase(TypedDict):
    name: str
    request: SimRequest
    expect_status: int


class TestResult(TypedDict):
    name: str
    request: SimRequest
    expect_status: int
    status: int
    passed: bool
    body: Any


class RunReport(TypedDict):
    ok: bool  # False when the code itself failed to load (syntax/import/definition error)
    error: str | None
    results: list[TestResult]


def load_app(source: str) -> Any:
    module = ModuleType("game_app")
    exec(compile(source, "<game>", "exec"), module.__dict__)  # noqa: S102 — sandboxed by caller
    app = module.__dict__.get("app")
    if app is None:
        raise RuntimeError("Game source did not define `app`")
    return app


async def run(source: str, tests: list[TestCase]) -> RunReport:
    try:
        app = load_app(source)
    except Exception:
        return {"ok": False, "error": _short_trace(), "results": []}
    results: list[TestResult] = []
    for test in tests:
        try:
            res: SimResponse = await call(app, test["request"])
        except Exception:
            # An unhandled exception inside the app is a 500: the "server crashed" animation.
            res = {"status": 500, "body": _short_trace()}
        results.append(
            {
                "name": test["name"],
                "request": test["request"],
                "expect_status": test["expect_status"],
                "status": res["status"],
                "passed": res["status"] == test["expect_status"],
                "body": res["body"],
            }
        )
    return {"ok": True, "error": None, "results": results}


def _short_trace(limit: int = 1500) -> str:
    text = traceback.format_exc(limit=3)
    return text[-limit:]
