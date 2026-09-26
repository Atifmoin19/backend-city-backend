"""Sandbox process entry point. Must NOT import anything from `app` (keeps secrets/config out).

Two modes, both run with the sandbox interpreter (`python -I -B entry.py <backend_root> ...`):

  cold   `entry.py <root>`: read one job as JSON on stdin, write a RunReport on stdout.
  warm   `entry.py <root> --serve`: a fork server. Imports FastAPI/Pydantic once, then for
         each job line on stdin forks a child that locks itself down and runs the job, so a
         grade costs milliseconds instead of a fresh interpreter + imports. Replies one JSON
         line per job on stdout.

A job is {"source": str, "tests": [...], "timeout": float, "memory_mb": int}. Tests carry
requests only: the parent keeps the expected results and does the scoring, so learner code
that forges output can't award itself passes.
"""

import asyncio
import contextlib
import io
import json
import os
import select
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any

_BLOCKED_EVENTS = (
    "socket.",
    "subprocess.",
    "os.system",
    "os.exec",
    "os.spawn",
    "os.fork",
    "os.posix_spawn",
    "os.kill",
    "os.remove",
    "os.rename",
    "os.rmdir",
    "os.mkdir",
    "shutil.",
    "ctypes.",
    "urllib.",
    "http.client.",
    "ftplib.",
    "smtplib.",
    "webbrowser.",
)
TIMEOUT_EXIT = 124
MAX_OUTPUT_BYTES = 256_000


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if event.startswith(_BLOCKED_EVENTS):
        raise PermissionError(f"Blocked by sandbox: {event}")
    if event == "open":
        mode = args[1] if len(args) > 1 else "r"
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            raise PermissionError("Blocked by sandbox: file write")
        if isinstance(mode, int) and mode & 0o3:  # os.open with O_WRONLY/O_RDWR
            raise PermissionError("Blocked by sandbox: file write")


class _CodeTimeout(BaseException):
    """BaseException so learner code's `except Exception` can't swallow the timer."""


def _on_alarm(_signum: int, _frame: object) -> None:
    raise _CodeTimeout


def _preimport() -> None:
    """Import everything a game may need BEFORE locking down."""
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401

    import harness.runner  # noqa: F401


def _run_locked(job: dict[str, Any]) -> dict[str, Any]:
    """Lock this process down (irreversibly) and run the job. Raises _CodeTimeout."""
    from harness.runner import run

    # The event loop opens its own self-pipe socket, so create it before the audit hook.
    loop = asyncio.new_event_loop()
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # learner print() output is captured, never mixed with result
    # The learner's time budget starts now, after the imports; the parent keeps a hard
    # wall-clock kill as a backstop in case this timer is swallowed.
    signal.signal(signal.SIGALRM, _on_alarm)
    sys.addaudithook(_audit)  # irreversible for the life of this process
    signal.setitimer(signal.ITIMER_REAL, float(job.get("timeout", 4)))
    try:
        report: dict[str, Any] = dict(loop.run_until_complete(run(job["source"], job["tests"])))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.stdout = real_stdout
    return report


# --- cold mode ---


def main_once() -> None:
    job = json.loads(sys.stdin.read())
    _preimport()
    try:
        report = _run_locked(job)
    except _CodeTimeout:
        sys.exit(TIMEOUT_EXIT)
    sys.stdout.write(json.dumps(report, default=str))
    sys.stdout.flush()


# --- warm mode (fork server) ---


def _limit_child(job: dict[str, Any]) -> None:  # pragma: no cover — runs in the forked child
    import resource

    cpu = int(float(job.get("timeout", 4))) + 1
    extra = int(job.get("memory_mb", 256)) * 1024 * 1024
    # RLIMIT_AS counts address space already mapped by the pre-imported server, so the
    # learner's allowance is added on top of what the child starts with (Linux only).
    base = 0
    with contextlib.suppress(OSError, ValueError), open("/proc/self/statm") as f:  # noqa: PTH123
        base = int(f.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
    for res, value in (
        (resource.RLIMIT_CPU, (cpu, cpu)),
        (resource.RLIMIT_FSIZE, (0, 0)),  # no file writes
        (resource.RLIMIT_NOFILE, (64, 64)),
        (resource.RLIMIT_AS, (base + extra, base + extra)),
    ):
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(res, value)


def _child(job: dict[str, Any], result_fd: int) -> None:  # pragma: no cover — forked child
    """Runs in the forked child: never returns."""
    code = 0
    try:
        os.setsid()
        # Learner code must only reach its own result pipe: not the server's stdin/stdout
        # (which lead back to the API) nor any other inherited descriptor.
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        for fd in range(3, 256):
            if fd != result_fd:
                with contextlib.suppress(OSError):
                    os.close(fd)
        _limit_child(job)
        report = _run_locked(job)
        data = json.dumps(report, default=str).encode()
        while data:
            data = data[os.write(result_fd, data) :]
    except _CodeTimeout:
        code = TIMEOUT_EXIT
    except BaseException:
        code = 1
    os._exit(code)


@dataclass
class _Running:
    """One forked child the server is waiting on."""

    job_id: object
    pid: int
    deadline: float
    chunks: list[bytes] = field(default_factory=list)
    size: int = 0


def _kill_group(pid: int) -> None:
    # OSError, not just ProcessLookupError: macOS answers EPERM for an already-dead group
    with contextlib.suppress(OSError):
        os.killpg(pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGKILL)


def _outcome(status: int, chunks: list[bytes]) -> tuple[str, Any]:
    exit_code = os.waitstatus_to_exitcode(status)
    # Out of CPU (RLIMIT_CPU sends SIGXCPU, then SIGKILL at the hard limit) is a timeout too
    if exit_code in (TIMEOUT_EXIT, -signal.SIGXCPU, -signal.SIGKILL):
        return "timeout", None
    if exit_code != 0:
        return "crashed", None
    try:
        return "ok", json.loads(b"".join(chunks))
    except ValueError:
        return "crashed", None


def _start(job: dict[str, Any]) -> tuple[int, _Running]:
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        _child(job, write_fd)
    os.close(write_fd)
    wall = float(job.get("timeout", 4)) + 1.0
    return read_fd, _Running(job.get("id"), pid, time.monotonic() + wall)


def serve(parallel: int = 1) -> None:
    """Read job lines on stdin; run up to `parallel` children at once; answer each with its
    id as soon as it finishes (replies can come out of order). Single-threaded on purpose:
    forking from a threaded process is unsafe, so one select() loop watches stdin and every
    child's result pipe, and enforces each child's deadline."""
    _preimport()
    out = sys.stdout
    out.write(json.dumps({"ready": True}) + "\n")
    out.flush()
    stdin = sys.stdin.fileno()
    buffer = b""
    waiting: list[dict[str, Any]] = []
    running: dict[int, _Running] = {}
    stdin_open = True

    def reply(job_id: object, outcome: str, report: Any) -> None:
        out.write(json.dumps({"id": job_id, "outcome": outcome, "report": report}) + "\n")
        out.flush()

    def finish(fd: int, killed: str = "") -> None:
        run = running.pop(fd)
        if killed:
            _kill_group(run.pid)
        os.close(fd)
        _, status = os.waitpid(run.pid, 0)
        outcome, report = (killed, None) if killed else _outcome(status, run.chunks)
        reply(run.job_id, outcome, report)

    while stdin_open or running or waiting:
        while waiting and len(running) < parallel:
            job = waiting.pop(0)
            try:
                fd, run = _start(job)
                running[fd] = run
            except Exception:  # one bad job must never take the server down
                reply(job.get("id"), "crashed", None)
        now = time.monotonic()
        timeout = max(0.0, min(r.deadline for r in running.values()) - now) if running else None
        ready, _, _ = select.select(
            ([stdin] if stdin_open else []) + list(running), [], [], timeout
        )
        for fd in ready:
            if fd == stdin:
                chunk = os.read(stdin, 65536)
                if not chunk:
                    stdin_open = False
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            waiting.append(json.loads(line))
                        except ValueError:
                            reply(None, "crashed", None)
                continue
            run = running[fd]
            chunk = os.read(fd, 65536)
            if not chunk:
                finish(fd)
                continue
            run.size += len(chunk)
            if run.size > MAX_OUTPUT_BYTES:
                finish(fd, killed="crashed")
            else:
                run.chunks.append(chunk)
        now = time.monotonic()
        for fd in [fd for fd, r in running.items() if r.deadline <= now]:
            finish(fd, killed="timeout")


if __name__ == "__main__":
    sys.path.insert(0, sys.argv[1])
    if "--serve" in sys.argv[2:]:
        flags = [a for a in sys.argv[2:] if a.startswith("--parallel=")]
        serve(max(1, int(flags[-1].split("=", 1)[1])) if flags else 1)
    else:
        main_once()
