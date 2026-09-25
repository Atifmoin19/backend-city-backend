"""Load a game's full source (starter + snippet) and run request tests against its `app`."""

import traceback
from types import ModuleType
from typing import Any, NotRequired, TypedDict

from harness.asgi import SimRequest, SimResponse, call


class TestCase(TypedDict):
    name: str
    request: SimRequest
    expect_status: int
    # Optional: the response JSON must contain these keys/values (a subset, not equality),
    # so routing games can check that the right handler answered. None = not checked.
    expect_body: NotRequired[Any]


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
                "passed": res["status"] == test["expect_status"] and _body_ok(res["body"], test),
                "body": res["body"],
            }
        )
    return {"ok": True, "error": None, "results": results}


def _body_ok(body: Any, test: TestCase) -> bool:
    expected = test.get("expect_body")
    return expected is None or contains(body, expected)


def contains(actual: Any, expected: Any) -> bool:
    """`expected` is a subset of `actual`: dict keys recursively, anything else must be equal."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and contains(actual[k], v) for k, v in expected.items()
        )
    return bool(actual == expected)


def _short_trace(limit: int = 1500) -> str:
    text = traceback.format_exc(limit=3)
    return text[-limit:]
