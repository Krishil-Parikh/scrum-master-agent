"""The completion gate (phased plan §2.3, §7.2, §7.3).

A task is only ``DONE`` when *the system* can confirm it — never because the
agent said so. We check three things independently:

1. **Implementation present** — there is a real diff against the task's base commit.
2. **Tests pass** — the project's test command exits clean with parseable results.
3. **Acceptance criteria** — every criterion with a ``check`` command exits 0;
   criteria without a check are reported as ``unverified`` (a reviewer agent /
   LLM judge closes that gap in Phase 6–7).

Code review is a fourth gate that arrives in Phase 6; until then
``review_required`` is False.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Settings, get_settings
from ..models.task import Task
from ..tools.test_runner import TestOutcome, run_tests
from ..tools.workspace import Workspace


@dataclass
class CriterionResult:
    text: str
    status: str          # "pass" | "fail" | "unverified"
    detail: str = ""


@dataclass
class VerificationReport:
    implementation_present: bool
    diff_stat: str
    tests: TestOutcome | None
    criteria: list[CriterionResult] = field(default_factory=list)
    review_required: bool = False
    review_passed: bool = False
    tests_required: bool = True   # does *this* task need a passing suite?
    notes: list[str] = field(default_factory=list)

    @property
    def tests_passed(self) -> bool:
        return bool(self.tests and self.tests.passed)

    @property
    def tests_ok(self) -> bool:
        """Test gate: a passing suite, or 'no tests' when this task didn't need any."""
        if self.tests is None:
            return not self.tests_required
        if getattr(self.tests, "no_tests", False):
            # empty suite: neither pass nor fail — acceptable only if not required
            return not self.tests_required
        return self.tests.passed

    @property
    def criteria_ok(self) -> bool:
        return all(c.status != "fail" for c in self.criteria)

    @property
    def passed(self) -> bool:
        gate = self.implementation_present and self.tests_ok and self.criteria_ok
        if self.review_required:
            gate = gate and self.review_passed
        return gate

    def render(self) -> str:
        lines = [
            f"implementation_present: {self.implementation_present}",
            f"tests_passed:           {self.tests_passed}",
            f"criteria_ok:            {self.criteria_ok}",
        ]
        if self.review_required:
            lines.append(f"review_passed:          {self.review_passed}")
        lines.append(f"tests_required:         {self.tests_required}  (ok={self.tests_ok})")
        lines.append(f"=> VERDICT: {'PASS' if self.passed else 'FAIL'}")
        if self.diff_stat:
            lines.append("\n" + self.diff_stat.strip())
        for c in self.criteria:
            lines.append(f"  [{c.status:10}] {c.text}" + (f" — {c.detail}" if c.detail else ""))
        if self.tests:
            lines.append("\n" + self.tests.render())
        if self.notes:
            lines.append("\n" + "\n".join(f"note: {n}" for n in self.notes))
        return "\n".join(lines)

    def feedback_for_agent(self) -> str:
        """Actionable failure context handed back to the agent for another attempt."""
        parts = ["Your previous attempt did NOT pass verification.\n"]
        if not self.implementation_present:
            parts.append("- No code changes were detected. You must actually edit files.")
        if self.tests and not self.tests_ok:
            if getattr(self.tests, "no_tests", False):
                parts.append(
                    "- This task needs tests but pytest collected none. Add tests "
                    "that actually run and cover the behaviour you changed."
                )
            else:
                parts.append("- The test suite is failing. Fix it:\n" + self.tests.render())
        for c in self.criteria:
            if c.status == "fail":
                parts.append(f"- Acceptance criterion still failing: {c.text}\n  {c.detail}")
        return "\n".join(parts)


def _llm_judge(
    task: Task,
    ws: Workspace,
    criteria: list[str],
    base_commit: str | None,
    settings: Settings,
) -> dict[str, tuple[bool, str]]:
    """Grade check-less acceptance criteria against the diff. Fail-open on error."""
    import json
    import re

    try:
        from ..llm.provider import build_chat_model

        diff = (ws.git(f"diff {base_commit}..HEAD").stdout if base_commit
                else ws.git("show HEAD").stdout)[:10000]
        model = build_chat_model(model=settings.reviewer_model, settings=settings, max_tokens=800)
        crit_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
        resp = model.invoke([
            ("system", "You grade acceptance criteria against a code diff. Reply ONLY with "
                       'JSON: {"results":[{"n":1,"met":true,"why":"..."}]}'),
            ("user", f"Task: {task.title}\n{task.description}\n\nCriteria:\n{crit_list}\n\n"
                     f"Diff:\n```diff\n{diff}\n```"),
        ])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        out: dict[str, tuple[bool, str]] = {}
        for r in data.get("results", []):
            idx = int(r.get("n", 0)) - 1
            if 0 <= idx < len(criteria):
                out[criteria[idx]] = (bool(r.get("met", True)), str(r.get("why", "")))
        return out
    except Exception:  # noqa: BLE001
        return {}


def _diff_against_base(ws: Workspace, base_commit: str | None) -> tuple[bool, str]:
    if base_commit:
        res = ws.git(f"diff --stat {base_commit} -- .")
        stat = res.stdout.strip()
        if stat:
            return True, stat
    # fall back to any tracked-or-untracked change in the tree
    porcelain = ws.status_porcelain().strip()
    if porcelain:
        return True, ws.git("diff --stat HEAD").stdout.strip() or porcelain
    return False, ""


_TEST_WORDS = ("test", "pytest", "coverage", "unittest", "assert", "spec")


def _task_requires_tests(task: Task) -> bool:
    """Scaffolding / config / docs tasks don't; anything code-bearing or QA does."""
    text = f"{task.title} {task.description}".lower()
    if task.role == "qa" or any(w in text for w in _TEST_WORDS):
        return True
    scaffold = ("scaffold", "directory structure", "project structure", "initial files",
                "boilerplate", "readme", "documentation", "configure ", "config file",
                "gitignore", "license", "folder")
    if any(s in text for s in scaffold):
        return False
    # a criterion that already has an executable check can stand in for tests
    if task.acceptance_criteria and all(c.check for c in task.acceptance_criteria):
        return False
    return True


def verify_task(
    task: Task,
    workspace: Workspace,
    *,
    base_commit: str | None = None,
    settings: Settings | None = None,
    run_test_suite: bool = True,
) -> VerificationReport:
    settings = settings or get_settings()
    ws = workspace

    present, diff_stat = _diff_against_base(ws, base_commit)

    tests: TestOutcome | None = None
    if run_test_suite:
        tests = run_tests(ws, settings.test_command, timeout=settings.agent_timeout_seconds)

    criteria: list[CriterionResult] = []
    uncheckable: list[str] = []
    for crit in task.acceptance_criteria:
        if not crit.check:
            criteria.append(CriterionResult(crit.text, "unverified", "no check command"))
            uncheckable.append(crit.text)
            continue
        res = ws.run(crit.check, timeout=180)
        criteria.append(
            CriterionResult(
                crit.text,
                "pass" if res.ok else "fail",
                f"exit={res.exit_code}: {(res.stderr or res.stdout).strip()[:400]}",
            )
        )

    # Phase 7 — LLM judge closes the gap for criteria with no executable check.
    if uncheckable and getattr(settings, "enable_llm_judge", False):
        judged = _llm_judge(task, ws, uncheckable, base_commit, settings)
        for cr in criteria:
            if cr.status == "unverified" and cr.text in judged:
                verdict = judged[cr.text]
                cr.status = "pass" if verdict[0] else "fail"
                cr.detail = f"llm-judge: {verdict[1][:300]}"

    report = VerificationReport(
        implementation_present=present,
        diff_stat=diff_stat,
        tests=tests,
        criteria=criteria,
        tests_required=_task_requires_tests(task),
    )
    if tests and tests.no_tests and not report.tests_required:
        report.notes.append("no tests needed for this task type; empty suite accepted")
    if not present:
        report.notes.append("no diff vs base commit — agent may have only claimed completion")
    return report
