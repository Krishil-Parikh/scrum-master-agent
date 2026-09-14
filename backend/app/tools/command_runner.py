"""Subprocess execution, scoped to an explicit working directory with a
timeout. Always invoked as an argv list (never `shell=True`) so a
model-generated string (a commit message, a filename) can never be
interpreted as shell syntax -- it's just one argument, however it's
punctuated."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ai_dev_pod.tools")

DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def combined_output(self) -> str:
        parts = []
        if self.stdout.strip():
            parts.append(self.stdout.strip())
        if self.stderr.strip():
            parts.append(self.stderr.strip())
        return "\n".join(parts)


def run_command(
    cwd: Path,
    args: list[str],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    check: bool = False,
) -> CommandResult:
    command_str = " ".join(args)
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            command=command_str,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=f"Command timed out after {timeout}s: {exc.stderr or ''}",
        )
        logger.warning("Command timed out: %s (cwd=%s)", command_str, cwd)
        if check:
            raise
        return result
    except FileNotFoundError as exc:
        result = CommandResult(command=command_str, returncode=127, stdout="", stderr=str(exc))
        if check:
            raise
        return result

    result = CommandResult(
        command=command_str, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
    )
    if check and not result.ok:
        raise RuntimeError(f"Command failed ({result.returncode}): {command_str}\n{result.combined_output}")
    return result
