"""Run game source + tests in an isolated, resource-limited Python subprocess."""

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # contains harness/
ENTRY = Path(__file__).with_name("entry.py")
MAX_OUTPUT_BYTES = 256_000


@dataclass(frozen=True)
class SandboxLimits:
    timeout_seconds: float
    memory_mb: int


@dataclass(frozen=True)
class SandboxResult:
    report: dict[str, Any] | None
    timed_out: bool = False
    crashed: bool = False
    stderr: str = ""


def _apply_rlimits(limits: SandboxLimits) -> None:  # pragma: no cover — runs in child
    import resource

    cpu = int(limits.timeout_seconds) + 1
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


def _python() -> str:
    return get_settings().sandbox_python or sys.executable


async def execute(source: str, tests: list[dict[str, Any]], limits: SandboxLimits) -> SandboxResult:
    payload = json.dumps({"source": source, "tests": tests}).encode()
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
            env={"PATH": "/usr/bin:/bin", "HOME": workdir},  # never inherit app secrets
            preexec_fn=lambda: _apply_rlimits(limits),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload), timeout=limits.timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(report=None, timed_out=True)

    err = stderr.decode(errors="replace")[-2000:]
    if proc.returncode != 0 or len(stdout) > MAX_OUTPUT_BYTES:
        return SandboxResult(report=None, crashed=True, stderr=err)
    try:
        return SandboxResult(report=json.loads(stdout))
    except ValueError:
        return SandboxResult(report=None, crashed=True, stderr=err)
