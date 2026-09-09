"""Standardized test execution (phased plan §7.1).

Runs the project's configured test command inside a workspace and parses a
best-effort pass/fail summary. The raw output is always kept so a failing agent
gets real feedback (phased plan §7.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

from .workspace import CommandResult, Workspace

_PYTEST_SUMMARY = re.compile(
    r"(?:(\d+) passed)?(?:, )?(?:(\d+) failed)?(?:, )?(?:(\d+) error(?:s)?)?"
    r"(?:, )?(?:(\d+) skipped)?"
)


@dataclass
class TestOutcome:
    __test__: ClassVar[bool] = False   # not a pytest test class

    command: str
    ran: bool
    passed: bool
    exit_code: int
    n_passed: int = 0
    n_failed: int = 0
    n_errors: int = 0
    n_skipped: int = 0
    duration_s: float = 0.0
    output: str = ""
    notes: list[str] = field(default_factory=list)
    no_tests: bool = False   # command ran fine but there were 0 tests to collect

    @property
    def total(self) -> int:
        return self.n_passed + self.n_failed + self.n_errors + self.n_skipped

    def render(self) -> str:
        head = (
            f"tests: {'PASS' if self.passed else 'FAIL'} "
            f"(exit={self.exit_code}, {self.n_passed} passed, "
            f"{self.n_failed} failed, {self.n_errors} errors, {self.n_skipped} skipped)"
        )
        if self.notes:
            head += "\n" + "\n".join(f"note: {n}" for n in self.notes)
        return head + "\n\n" + self.output[-8000:]


def _parse_pytest(text: str) -> tuple[int, int, int, int]:
    n_passed = n_failed = n_errors = n_skipped = 0
    for line in text.splitlines():
        if "passed" in line or "failed" in line or "error" in line:
            m = _PYTEST_SUMMARY.search(line)
            if m and any(m.groups()):
                n_passed = max(n_passed, int(m.group(1) or 0))
                n_failed = max(n_failed, int(m.group(2) or 0))
                n_errors = max(n_errors, int(m.group(3) or 0))
                n_skipped = max(n_skipped, int(m.group(4) or 0))
    return n_passed, n_failed, n_errors, n_skipped


def run_tests(workspace: Workspace, command: str, *, timeout: int = 600) -> TestOutcome:
    result: CommandResult = workspace.run(command, timeout=timeout)
    outcome = TestOutcome(
        command=command,
        ran=not result.timed_out,
        passed=result.ok,
        exit_code=result.exit_code,
        duration_s=result.duration_s,
        output=result.render(limit=12000),
    )
    if result.timed_out:
        outcome.notes.append(f"test command timed out after {timeout}s")
        outcome.passed = False
        return outcome

    combined = f"{result.stdout}\n{result.stderr}"
    if "pytest" in command or "py.test" in command:
        p, f, e, s = _parse_pytest(combined)
        outcome.n_passed, outcome.n_failed, outcome.n_errors, outcome.n_skipped = p, f, e, s
        if result.exit_code == 5 and outcome.total == 0:
            # exit 5 == "no tests collected". Not a failure on its own — the
            # verification gate decides whether *this* task needed tests.
            outcome.no_tests = True
            outcome.passed = True
            outcome.notes.append("pytest collected no tests (exit 5)")
            return outcome
    if result.exit_code != 0 and outcome.total == 0:
        outcome.notes.append("no parseable test summary; treating non-zero exit as failure")
    return outcome
