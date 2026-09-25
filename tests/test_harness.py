import pytest

from harness.runner import run
from harness.splice import SpliceError, splice

REGION = {"start_marker": "# >>> EDIT START", "end_marker": "# <<< EDIT END"}
STARTER = "class A:\n    # >>> EDIT START\n    pass\n    # <<< EDIT END\n"


def test_splice_replaces_region_and_keeps_indent() -> None:
    out = splice(STARTER, "x: int = 1\ny: int = 2", REGION)  # type: ignore[arg-type]
    assert "    x: int = 1\n    y: int = 2\n" in out
    assert "    pass" not in out


def test_splice_empty_snippet_becomes_pass() -> None:
    assert "    pass" in splice(STARTER, "   ", REGION)  # type: ignore[arg-type]


def test_splice_missing_markers() -> None:
    with pytest.raises(SpliceError):
        splice("x = 1\n", "y = 2", REGION)  # type: ignore[arg-type]


APP = """
from fastapi import FastAPI
from pydantic import BaseModel, Field
app = FastAPI()
class Body(BaseModel):
    n: int = Field(ge=0)
@app.post("/n")
async def n(b: Body) -> dict[str, int]:
    return {"n": 10 // b.n}
"""


async def test_runner_reports_pass_bounce_and_crash() -> None:
    tests = [
        {
            "name": "ok",
            "request": {"method": "POST", "path": "/n", "json": {"n": 2}},
            "expect_status": 200,
        },
        {
            "name": "bounce",
            "request": {"method": "POST", "path": "/n", "json": {"n": -1}},
            "expect_status": 422,
        },
        {
            "name": "crash",
            "request": {"method": "POST", "path": "/n", "json": {"n": 0}},
            "expect_status": 200,
        },
    ]
    report = await run(APP, tests)  # type: ignore[arg-type]
    assert report["ok"]
    assert [r["status"] for r in report["results"]] == [200, 422, 500]
    assert [r["passed"] for r in report["results"]] == [True, True, False]


async def test_runner_reports_load_error() -> None:
    report = await run("app = undefined_name", [])
    assert not report["ok"]
    assert "NameError" in (report["error"] or "")
