import sys

import pytest

from app.sandbox.executor import SandboxLimits, execute
from app.sandbox.policy import check_snippet

LIMITS = SandboxLimits(timeout_seconds=4, memory_mb=256)


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


async def test_sandbox_times_out_infinite_loop() -> None:
    result = await execute("while True:\n    pass\n", [], SandboxLimits(1.0, 256))
    assert result.timed_out


async def test_code_timer_cannot_be_swallowed_by_except_exception() -> None:
    src = (
        "while True:\n    try:\n        while True:\n            pass\n"
        "    except Exception:\n        pass\n"
    )
    result = await execute(src, [], SandboxLimits(1.0, 256))
    assert result.timed_out


async def test_wall_clock_backstop_kills_code_that_swallows_the_timer() -> None:
    src = (
        "while True:\n    try:\n        while True:\n            pass\n"
        "    except BaseException:\n        pass\n"
    )
    result = await execute(src, [], SandboxLimits(1.0, 256, startup_seconds=3.0))
    assert result.timed_out


async def test_sandbox_blocks_network() -> None:
    src = "import socket\nsocket.create_connection(('example.com', 80), timeout=1)\napp = None\n"
    result = await execute(src, [], LIMITS)
    assert result.report is not None
    assert not result.report["ok"]
    assert "Blocked by sandbox" in result.report["error"]


async def test_sandbox_blocks_file_writes() -> None:
    src = "with open('pwned.txt', 'w') as f:\n    f.write('x')\napp = None\n"
    result = await execute(src, [], LIMITS)
    assert result.report is not None
    assert "Blocked by sandbox" in result.report["error"]


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


async def test_sandbox_captures_print_output() -> None:
    result = await execute("print('noise')\napp = object()\n", [], LIMITS)
    assert result.report is not None
    assert result.report["ok"]


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is only enforced on Linux")
async def test_sandbox_enforces_memory_limit() -> None:
    result = await execute("x = bytearray(1024 * 1024 * 1024)\napp = None\n", [], LIMITS)
    assert result.report is None or not result.report["ok"]
