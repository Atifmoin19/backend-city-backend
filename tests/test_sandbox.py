import sys
from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.sandbox.executor import SandboxLimits, execute
from app.sandbox.policy import check_snippet

LIMITS = SandboxLimits(timeout_seconds=4, memory_mb=256)


@pytest.fixture(params=["warm", "cold"])
def engine(request: pytest.FixtureRequest) -> Iterator[str]:
    """Every runtime defense must hold for both the fork server and fresh interpreters."""
    settings = get_settings()
    before = settings.sandbox_warm
    settings.sandbox_warm = request.param == "warm"
    yield request.param
    settings.sandbox_warm = before


@pytest.mark.parametrize(
    ("snippet", "fragment"),
    [
        ("import os", "Import not allowed: os"),
        ("from subprocess import run", "Import not allowed: subprocess"),
        ("x = ().__class__.__bases__", "Dunder attribute"),
        ("eval('1+1')", "`eval`"),
        ("open('/etc/passwd')", "`open`"),
        ("from . import thing", "Import not allowed"),
        ("def f(:\n  pass", "Syntax error"),
    ],
)
def test_policy_rejects_dangerous_snippets(snippet: str, fragment: str) -> None:
    violations = check_snippet(snippet, max_chars=4000)
    assert violations
    assert any(fragment in v.message for v in violations)


def test_policy_allows_normal_pydantic_code() -> None:
    snippet = "from pydantic import Field\nage: int = Field(ge=13, le=120)\n"
    assert check_snippet(snippet, max_chars=4000) == []


def test_policy_rejects_oversized_snippet() -> None:
    assert "too long" in check_snippet("x = 1\n" * 1000, max_chars=100)[0].message


# --- runtime defenses (these bypass the AST policy on purpose) ---

pytestmark_engine = pytest.mark.usefixtures("engine")


@pytestmark_engine
async def test_sandbox_times_out_infinite_loop() -> None:
    result = await execute("while True:\n    pass\n", [], SandboxLimits(1.0, 256))
    assert result.timed_out


@pytestmark_engine
async def test_code_timer_cannot_be_swallowed_by_except_exception() -> None:
    src = (
        "while True:\n    try:\n        while True:\n            pass\n"
        "    except Exception:\n        pass\n"
    )
    result = await execute(src, [], SandboxLimits(1.0, 256))
    assert result.timed_out


@pytestmark_engine
async def test_wall_clock_backstop_kills_code_that_swallows_the_timer() -> None:
    src = (
        "while True:\n    try:\n        while True:\n            pass\n"
        "    except BaseException:\n        pass\n"
    )
    result = await execute(src, [], SandboxLimits(1.0, 256, startup_seconds=3.0))
    assert result.timed_out


@pytestmark_engine
async def test_sandbox_blocks_network() -> None:
    src = "import socket\nsocket.create_connection(('example.com', 80), timeout=1)\napp = None\n"
    result = await execute(src, [], LIMITS)
    assert result.report is not None
    assert not result.report["ok"]
    assert "Blocked by sandbox" in result.report["error"]


@pytestmark_engine
async def test_sandbox_blocks_file_writes() -> None:
    src = "with open('pwned.txt', 'w') as f:\n    f.write('x')\napp = None\n"
    result = await execute(src, [], LIMITS)
    assert result.report is not None
    assert "Blocked by sandbox" in result.report["error"]


@pytestmark_engine
async def test_sandbox_does_not_leak_env_secrets() -> None:
    src = (
        "import os\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/env')\n"
        "async def env() -> dict[str, str]:\n"
        "    return dict(os.environ)\n"
    )
    tests = [{"name": "env", "request": {"method": "GET", "path": "/env"}, "expect_status": 200}]
    result = await execute(src, tests, LIMITS)
    assert result.report is not None
    body = result.report["results"][0]["body"]
    assert "JWT_SECRET" not in body
    assert "DATABASE_URL" not in body


@pytestmark_engine
async def test_sandbox_captures_print_output() -> None:
    result = await execute("print('noise')\napp = object()\n", [], LIMITS)
    assert result.report is not None
    assert result.report["ok"]


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is only enforced on Linux")
@pytestmark_engine
async def test_sandbox_enforces_memory_limit() -> None:
    result = await execute("x = bytearray(1024 * 1024 * 1024)\napp = None\n", [], LIMITS)
    assert result.report is None or not result.report["ok"]


FORGED = """
import uuid
row = '{"name": "x", "request": {}, "expect_status": 201, "status": 201, "passed": true}'
fake = '{"ok": true, "error": null, "results": [' + ','.join([row] * 3) + ']}'
uuid.os.write(1, fake.encode())
uuid.os._exit(0)
"""


@pytestmark_engine
async def test_forged_report_cannot_award_passes() -> None:
    """Allowed modules expose `os` (uuid.os); a child writing its own verdict must not score."""
    assert check_snippet(FORGED, max_chars=4000) == []  # the AST policy alone can't stop this
    tests = [
        {"name": "t", "request": {"method": "GET", "path": "/"}, "expect_status": 201},
        {"name": "u", "request": {"method": "GET", "path": "/u"}, "expect_status": 422},
    ]
    result = await execute("from fastapi import FastAPI\napp = FastAPI()\n" + FORGED, tests, LIMITS)
    passed = sum(r["passed"] for r in result.report["results"]) if result.report else 0
    assert passed == 0


@pytestmark_engine
async def test_child_never_sees_expected_results() -> None:
    src = (
        "from fastapi import FastAPI, Request\n"
        "app = FastAPI()\n"
        "@app.get('/')\n"
        "async def peek() -> dict[str, object]:\n"
        "    import gc\n"
        "    found = [o for o in gc.get_objects() if isinstance(o, dict)]\n"
        "    return {'leak': [o for o in found if o.get('expect_status') == 418]}\n"
    )
    tests = [{"name": "t", "request": {"method": "GET", "path": "/"}, "expect_status": 418}]
    result = await execute(src, tests, LIMITS)
    assert result.report is not None
    assert result.report["results"][0]["body"] == {"leak": []}


@pytestmark_engine
async def test_scores_statuses_and_bodies_in_the_parent() -> None:
    src = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/t/{i}')\n"
        "async def t(i: int) -> dict[str, int]:\n"
        "    return {'id': i}\n"
    )
    tests = [
        {
            "name": "a",
            "request": {"method": "GET", "path": "/t/1"},
            "expect_status": 200,
            "expect_body": {"id": 1},
        },
        {
            "name": "b",
            "request": {"method": "GET", "path": "/t/2"},
            "expect_status": 200,
            "expect_body": {"id": 3},
        },
        {"name": "c", "request": {"method": "GET", "path": "/t/x"}, "expect_status": 422},
    ]
    result = await execute(src, tests, LIMITS)
    assert result.report is not None
    assert [r["passed"] for r in result.report["results"]] == [True, False, True]


async def test_warm_engine_is_fast_after_the_first_grade() -> None:
    import time

    settings = get_settings()
    settings.sandbox_warm = True
    tests = [{"name": "t", "request": {"method": "GET", "path": "/"}, "expect_status": 404}]
    src = "from fastapi import FastAPI\napp = FastAPI()\n"
    await execute(src, tests, LIMITS)  # starts the server if needed
    start = time.monotonic()
    for _ in range(3):
        result = await execute(src, tests, LIMITS)
        assert result.report is not None and result.report["results"][0]["passed"]
    assert (time.monotonic() - start) / 3 < 1.0


async def test_warm_engine_grades_in_parallel_and_matches_replies() -> None:
    """Several grades at once: each caller gets its own report back, in any order."""
    import asyncio

    settings = get_settings()
    settings.sandbox_warm = True
    src = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/n')\n"
        "async def n() -> dict[str, int]:\n"
        "    return {'n': N}\n"
    )
    tests = [{"name": "n", "request": {"method": "GET", "path": "/n"}, "expect_status": 200}]
    results = await asyncio.gather(
        *(execute(src.replace("N", str(i)), tests, LIMITS) for i in range(6))
    )
    bodies = [r.report["results"][0]["body"] for r in results if r.report is not None]
    assert bodies == [{"n": i} for i in range(6)]


async def test_a_runaway_grade_does_not_hold_up_a_quick_one() -> None:
    import asyncio
    import time

    settings = get_settings()
    settings.sandbox_warm = True
    quick_src = "from fastapi import FastAPI\napp = FastAPI()\n"
    tests = [{"name": "t", "request": {"method": "GET", "path": "/"}, "expect_status": 404}]
    await execute(quick_src, tests, LIMITS)  # server up
    slow = asyncio.create_task(execute("while True:\n    pass\n", [], SandboxLimits(2.0, 256)))
    await asyncio.sleep(0.2)
    start = time.monotonic()
    quick = await execute(quick_src, tests, LIMITS)
    assert quick.report is not None and quick.report["results"][0]["passed"]
    assert time.monotonic() - start < 1.5  # did not wait for the 2 s loop
    assert (await slow).timed_out


SQL_APP = (
    "import sqlite3\n"
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    "@app.get('/q')\n"
    "async def q() -> dict[str, object]:\n"
    "    db = sqlite3.connect(DB)\n"
    "    db.execute('CREATE TABLE t (n INTEGER)')\n"
    "    db.executemany('INSERT INTO t VALUES (?)', [(1,), (2,), (3,)])\n"
    "    EXTRA\n"
    "    return {'sum': db.execute('SELECT sum(n) FROM t').fetchone()[0]}\n"
)
SQL_TEST = [{"name": "q", "request": {"method": "GET", "path": "/q"}, "expect_status": 200}]


def sql_app(db: str = "':memory:'", extra: str = "pass") -> str:
    return SQL_APP.replace("DB", db).replace("EXTRA", extra)


@pytestmark_engine
async def test_sqlite_in_memory_works() -> None:
    result = await execute(sql_app(), SQL_TEST, LIMITS)
    assert result.report is not None
    assert result.report["results"][0]["body"] == {"sum": 6}


@pytestmark_engine
@pytest.mark.parametrize(
    ("db", "extra"),
    [
        ("'/tmp/vault.db'", "pass"),  # a database file
        ("'file:x?mode=memory'", "pass"),  # URI tricks count as files too
        ("':memory:'", "db.enable_load_extension(True)"),
        ("':memory:'", "sqlite3.Connection('/tmp/y.db')"),
    ],
)
async def test_sqlite_cannot_reach_the_filesystem(db: str, extra: str) -> None:
    result = await execute(sql_app(db, extra), SQL_TEST, LIMITS)
    assert result.report is not None
    assert result.report["results"][0]["status"] == 500  # the handler was stopped


@pytestmark_engine
async def test_the_vault_refuses_attach() -> None:
    src = (
        "from fastapi import FastAPI\n"
        "from harness.vault import open_vault\n"
        "db = open_vault('CREATE TABLE t (n INTEGER); INSERT INTO t VALUES (7);')\n"
        "app = FastAPI()\n"
        "@app.get('/ok')\n"
        "async def ok() -> dict[str, int]:\n"
        "    return {'n': db.execute('SELECT n FROM t').fetchone()[0]}\n"
        "@app.get('/attach')\n"
        "async def attach() -> dict[str, str]:\n"
        "    db.execute(\"ATTACH DATABASE '/tmp/x.db' AS x\")\n"
        "    return {'x': 'attached'}\n"
    )
    tests = [
        {"name": "ok", "request": {"method": "GET", "path": "/ok"}, "expect_status": 200},
        {"name": "attach", "request": {"method": "GET", "path": "/attach"}, "expect_status": 500},
    ]
    result = await execute(src, tests, LIMITS)
    assert result.report is not None
    ok, attach = result.report["results"]
    assert ok["body"] == {"n": 7}
    assert attach["status"] == 500


@pytest.mark.parametrize(
    "snippet",
    [
        "db.set_authorizer(None)",
        "db.setlimit(10, 10)",
        "db.enable_load_extension(True)",
        "import sqlite3",
    ],
)
def test_policy_protects_the_vault_guard(snippet: str) -> None:
    assert check_snippet(snippet, max_chars=500)
