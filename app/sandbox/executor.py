"""Run game source + tests in an isolated, resource-limited Python process.

Two engines, same result:
  * warm (default): a long-lived fork server with FastAPI/Pydantic already imported forks
    one locked-down child per grade (~milliseconds of startup instead of seconds on a
    small CPU);
  * cold: a fresh interpreter per grade (fallback when the fork server can't start).

Scoring happens HERE, never in the sandbox: children only receive the requests, and their
report is checked against the expected results that stay in this process.
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from harness.runner import contains

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # contains harness/
ENTRY = Path(__file__).with_name("entry.py")
MAX_OUTPUT_BYTES = 256_000
TIMEOUT_EXIT = 124  # child exit code when the in-process code timer fires
SANDBOX_ENV = {"PATH": "/usr/bin:/bin"}  # never inherit app secrets

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxLimits:
    timeout_seconds: float  # learner code budget, measured after imports (enforced in-child)
    memory_mb: int
    # Interpreter start + FastAPI/Pydantic imports. Not charged to the learner: on a small
    # shared CPU (Render free) this alone can take several seconds.
    startup_seconds: float = 20.0

    @property
    def wall_seconds(self) -> float:
        return self.startup_seconds + self.timeout_seconds


@dataclass(frozen=True)
class SandboxResult:
    report: dict[str, Any] | None
    timed_out: bool = False
    crashed: bool = False
    stderr: str = ""


def _python() -> str:
    return get_settings().sandbox_python or sys.executable


def _requests_only(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the child may see: names and requests, no expected results."""
    return [{"name": t["name"], "request": t["request"], "expect_status": 0} for t in tests]


def score(tests: list[dict[str, Any]], raw: Any) -> SandboxResult:
    """Validate a child's report and decide pass/fail here, from our own expectations."""
    if not isinstance(raw, dict) or not isinstance(raw.get("ok"), bool):
        return SandboxResult(report=None, crashed=True)
    if not raw["ok"]:
        return SandboxResult(report={"ok": False, "error": str(raw.get("error")), "results": []})
    results = raw.get("results")
    if not isinstance(results, list) or len(results) != len(tests):
        return SandboxResult(report=None, crashed=True)
    scored = []
    for test, got in zip(tests, results, strict=True):
        status = got.get("status") if isinstance(got, dict) else None
        if not isinstance(status, int) or isinstance(status, bool):
            return SandboxResult(report=None, crashed=True)
        body = got.get("body")
        expected_body = test.get("expect_body")
        scored.append(
            {
                "name": test["name"],
                "request": test["request"],
                "expect_status": test["expect_status"],
                "status": status,
                "passed": status == test["expect_status"]
                and (expected_body is None or contains(body, expected_body)),
                "body": body,
            }
        )
    return SandboxResult(report={"ok": True, "error": None, "results": scored})


async def execute(source: str, tests: list[dict[str, Any]], limits: SandboxLimits) -> SandboxResult:
    job = {
        "source": source,
        "tests": _requests_only(tests),
        "timeout": limits.timeout_seconds,
        "memory_mb": limits.memory_mb,
    }
    if get_settings().sandbox_warm:
        try:
            outcome, raw = await warm_sandbox.run(job, limits)
        except WarmUnavailableError:
            log.warning("warm sandbox unavailable; grading with a cold interpreter")
        else:
            if outcome == "timeout":
                return SandboxResult(report=None, timed_out=True)
            if outcome != "ok":
                return SandboxResult(report=None, crashed=True)
            return score(tests, raw)
    return await _execute_cold(job, tests, limits)


# --- cold engine ---


def _apply_rlimits(limits: SandboxLimits) -> None:  # pragma: no cover — runs in child
    import resource

    cpu = int(limits.wall_seconds) + 1
    mem = limits.memory_mb * 1024 * 1024
    for res, value in (
        (resource.RLIMIT_CPU, (cpu, cpu)),
        (resource.RLIMIT_FSIZE, (0, 0)),  # no file writes
        (resource.RLIMIT_NOFILE, (64, 64)),
        (resource.RLIMIT_AS, (mem, mem)),  # enforced on Linux; macOS ignores/rejects it
    ):
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(res, value)
    os.setsid()


async def _execute_cold(
    job: dict[str, Any], tests: list[dict[str, Any]], limits: SandboxLimits
) -> SandboxResult:
    with tempfile.TemporaryDirectory(prefix="bc-sbx-") as workdir:
        proc = await asyncio.create_subprocess_exec(
            _python(),
            "-I",  # isolated: ignore PYTHON* env vars and user site-packages
            "-B",  # no .pyc writes (RLIMIT_FSIZE is 0)
            str(ENTRY),
            str(BACKEND_ROOT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env={**SANDBOX_ENV, "HOME": workdir},
            preexec_fn=lambda: _apply_rlimits(limits),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(json.dumps(job).encode()), timeout=limits.wall_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(report=None, timed_out=True)

    if proc.returncode == TIMEOUT_EXIT:
        return SandboxResult(report=None, timed_out=True)
    err = stderr.decode(errors="replace")[-2000:]
    if proc.returncode != 0 or len(stdout) > MAX_OUTPUT_BYTES:
        return SandboxResult(report=None, crashed=True, stderr=err)
    try:
        return score(tests, json.loads(stdout))
    except ValueError:
        return SandboxResult(report=None, crashed=True, stderr=err)


# --- warm engine ---


class WarmUnavailableError(RuntimeError):
    pass


class WarmSandbox:
    """Client for the fork server (entry.py --serve). Up to `sandbox_parallel` jobs run at
    once; one reader task hands each reply (tagged with its job id) to the waiting caller.
    The server is restarted when it dies or stops answering."""

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._lock: asyncio.Lock | None = None  # guards start-up and writes to stdin
        self._slots: asyncio.Semaphore | None = None  # jobs in flight <= server parallelism
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reader: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[tuple[str, Any]]] = {}
        self._jobs = 0
        self._workdir = tempfile.mkdtemp(prefix="bc-warm-")

    @staticmethod
    def _parallel() -> int:
        return max(1, get_settings().sandbox_parallel)

    def _bind(self) -> tuple[asyncio.Lock, asyncio.Semaphore]:
        """The process, lock and reader belong to one event loop (tests may use several)."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop or self._lock is None or self._slots is None:
            self._loop, self._proc, self._reader = loop, None, None
            self._lock, self._slots = asyncio.Lock(), asyncio.Semaphore(self._parallel())
            self._pending = {}
        return self._lock, self._slots

    async def _start(self, startup_seconds: float) -> asyncio.subprocess.Process:
        try:
            proc = await asyncio.create_subprocess_exec(
                _python(),
                "-I",
                "-B",
                str(ENTRY),
                str(BACKEND_ROOT),
                "--serve",
                f"--parallel={self._parallel()}",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=self._workdir,
                env={**SANDBOX_ENV, "HOME": self._workdir},
                limit=MAX_OUTPUT_BYTES * 2,
            )
            assert proc.stdout is not None  # noqa: S101 — PIPE requested above
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=startup_seconds)
            if json.loads(line or b"{}").get("ready") is not True:
                raise WarmUnavailableError("fork server did not report ready")
        except (OSError, TimeoutError, ValueError) as exc:
            raise WarmUnavailableError(str(exc)) from exc
        self._reader = asyncio.create_task(self._read_replies(proc))
        return proc

    async def _read_replies(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None  # noqa: S101
        try:
            while line := await proc.stdout.readline():
                reply = json.loads(line)
                fut = self._pending.pop(reply.get("id"), None)
                if fut is not None and not fut.done():
                    fut.set_result((str(reply["outcome"]), reply.get("report")))
        except (OSError, ValueError, asyncio.LimitOverrunError):
            pass
        # the server is gone (or spoke nonsense): every job still waiting has crashed
        if self._proc is proc:
            self._proc = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result(("crashed", None))
        self._pending.clear()

    async def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()

    async def run(self, job: dict[str, Any], limits: SandboxLimits) -> tuple[str, Any]:
        lock, slots = self._bind()
        async with slots:
            async with lock:
                if self._proc is None or self._proc.returncode is not None:
                    self._proc = await self._start(limits.startup_seconds)
                proc = self._proc
                assert proc.stdin is not None  # noqa: S101
                self._jobs += 1
                job_id = self._jobs
                fut: asyncio.Future[tuple[str, Any]] = asyncio.get_running_loop().create_future()
                self._pending[job_id] = fut
                try:
                    proc.stdin.write(json.dumps({**job, "id": job_id}).encode() + b"\n")
                    await proc.stdin.drain()
                except OSError:
                    self._pending.pop(job_id, None)
                    await self._kill()
                    return "crashed", None
            try:
                # the server kills the child after timeout + 1 s; allow a margin on top
                return await asyncio.wait_for(fut, timeout=limits.timeout_seconds + 5)
            except TimeoutError:
                # the server itself stopped answering: restart it (other jobs fail with it)
                self._pending.pop(job_id, None)
                async with lock:
                    if self._proc is proc:
                        await self._kill()
                return "crashed", None

    async def warm_up(self) -> None:
        """Start the server ahead of the first grade (called at app startup)."""
        settings = get_settings()
        lock, _ = self._bind()
        async with lock:
            if self._proc is None:
                self._proc = await self._start(settings.sandbox_startup_seconds)


warm_sandbox = WarmSandbox()
