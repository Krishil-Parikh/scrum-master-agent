"""Branch integration with conflict + regression detection (phased plan §6.3-6.6)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Settings, get_settings
from ..tools.test_runner import TestOutcome, run_tests
from ..tools.workspace import Workspace


@dataclass
class IntegrationResult:
    merged: bool
    target: str
    source: str
    conflicts: list[str] = field(default_factory=list)
    regression: TestOutcome | None = None
    merge_commit: str | None = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.merged and not self.conflicts and (
            self.regression is None or self.regression.passed
        )

    def render(self) -> str:
        head = f"integrate {self.source} -> {self.target}: {'OK' if self.ok else 'FAILED'}"
        if self.conflicts:
            head += "\nconflicts:\n" + "\n".join(f"  {c}" for c in self.conflicts)
        if self.note:
            head += f"\n{self.note}"
        if self.regression:
            head += "\n" + self.regression.render()
        return head


def integrate_branch(
    workspace: Workspace,
    source_branch: str,
    *,
    target: str | None = None,
    settings: Settings | None = None,
    run_regression: bool = True,
) -> IntegrationResult:
    settings = settings or get_settings()
    target = target or settings.integration_target_branch
    ws = workspace

    if not settings.enable_integration:
        return IntegrationResult(merged=False, target=target, source=source_branch,
                                 note="integration disabled")

    # ensure target exists; create it from the first branch if this is the first merge
    have_target = ws.run_argv(["git", "rev-parse", "--verify", target]).ok
    if not have_target:
        ws.run_argv(["git", "branch", target])
        have_target = ws.run_argv(["git", "rev-parse", "--verify", target]).ok

    co = ws.run_argv(["git", "checkout", target])
    if not co.ok:
        return IntegrationResult(merged=False, target=target, source=source_branch,
                                 note=f"could not checkout {target}: {co.stderr.strip()[:200]}")

    merge = ws.run_argv(["git", "merge", "--no-ff", "-m", f"merge: {source_branch}", source_branch])
    if not merge.ok:
        status = ws.run_argv(["git", "diff", "--name-only", "--diff-filter=U"]).stdout
        conflicts = [ln.strip() for ln in status.splitlines() if ln.strip()]
        ws.run_argv(["git", "merge", "--abort"])
        return IntegrationResult(
            merged=False, target=target, source=source_branch, conflicts=conflicts,
            note=merge.stderr.strip()[:400] or "merge failed",
        )

    merge_commit = ws.last_commit_hash()
    regression: TestOutcome | None = None
    if run_regression:
        regression = run_tests(ws, settings.test_command, timeout=settings.agent_timeout_seconds)
        if not regression.passed and not regression.no_tests:
            # roll the mainline back — a red main is worse than an unmerged task
            ws.run_argv(["git", "reset", "--hard", "HEAD~1"])
            return IntegrationResult(
                merged=False, target=target, source=source_branch, regression=regression,
                note="merged then reverted: regression on target",
            )

    return IntegrationResult(
        merged=True, target=target, source=source_branch,
        regression=regression, merge_commit=merge_commit,
    )
