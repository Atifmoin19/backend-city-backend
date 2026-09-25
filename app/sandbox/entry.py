"""Sandbox subprocess entry point. Run as:  python -I entry.py <harness_parent_dir>

Reads {"source": str, "tests": [...]} as JSON on stdin, writes a RunReport JSON on stdout.
Must NOT import anything from `app` (keeps secrets/config out of the child process).
"""

import asyncio
import io
import json
import sys
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


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if event.startswith(_BLOCKED_EVENTS):
        raise PermissionError(f"Blocked by sandbox: {event}")
    if event == "open":
        mode = args[1] if len(args) > 1 else "r"
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            raise PermissionError("Blocked by sandbox: file write")
        if isinstance(mode, int) and mode & 0o3:  # os.open with O_WRONLY/O_RDWR
            raise PermissionError("Blocked by sandbox: file write")


def main() -> None:
    sys.path.insert(0, sys.argv[1])
    payload = json.loads(sys.stdin.read())

    # Import everything the game may need BEFORE locking down.
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401

    from harness.runner import run

    # The event loop opens its own self-pipe socket, so create it before the audit hook.
    loop = asyncio.new_event_loop()
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # learner print() output is captured, never mixed with result
    sys.addaudithook(_audit)  # irreversible for the life of this process
    try:
        report = loop.run_until_complete(run(payload["source"], payload["tests"]))
    finally:
        sys.stdout = real_stdout
    real_stdout.write(json.dumps(report, default=str))
    real_stdout.flush()


if __name__ == "__main__":
    main()
