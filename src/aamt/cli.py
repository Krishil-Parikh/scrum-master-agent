"""``aamt`` command-line entrypoint.

Phase 1 surface: inspect configuration and drive a *single* developer agent
through the task-execution loop (Milestone 1 — "agent can code").
Sprint/standup/report commands arrive with later phases.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .bootstrap import load_env
from .config import get_settings

app = typer.Typer(add_completion=False, help="Autonomous Agile Multi-Agent Software Engineering Team")
console = Console()


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"aamt {__version__}")


@app.command()
def doctor() -> None:
    """Check configuration, provider credentials and tooling."""
    load_env()
    s = get_settings(reload=True)

    table = Table(title="aamt doctor", show_header=False)
    table.add_row("provider", s.llm_provider)
    table.add_row("developer model", s.developer_model)
    table.add_row("data dir", str(s.data_dir.resolve()))
    table.add_row("test command", s.test_command)

    ok = True
    if s.llm_provider == "openrouter":
        keys = s.resolved_openrouter_keys()
        table.add_row("openrouter keys", f"{len(keys)} found" if keys else "[red]NONE[/red]")
        ok = ok and bool(keys)
    else:
        import os

        env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure_openai": "AZURE_OPENAI_API_KEY",
        }.get(s.llm_provider)
        if env:
            present = bool(os.environ.get(env))
            table.add_row(env, "set" if present else "[red]missing[/red]")
            ok = ok and present

    import shutil

    table.add_row("git", shutil.which("git") or "[red]not found[/red]")
    ok = ok and bool(shutil.which("git"))

    console.print(table)
    if not ok:
        console.print("[red]doctor: problems found[/red]")
        raise typer.Exit(1)
    console.print("[green]doctor: ok[/green]")


@app.command("run-task")
def run_task_cmd(
    repo: Path = typer.Option(..., "--repo", "-r", help="Path to the target git repo/dir."),
    title: str = typer.Option(..., "--title", "-t", help="Task title."),
    description: str = typer.Option("", "--description", "-d", help="Task description."),
    role: str = typer.Option("backend", "--role", help="Developer role: backend|frontend|database|ml|qa|devops."),
    criterion: list[str] = typer.Option(None, "--criterion", "-c", help="Acceptance criterion (repeatable)."),
    check: list[str] = typer.Option(None, "--check", help="Shell check for the i-th criterion (repeatable, positional)."),
    attempts: int = typer.Option(None, "--attempts", help="Max attempts (default from config)."),
) -> None:
    """Run one developer agent on one task against --repo, with the verification gate."""
    load_env()
    s = get_settings(reload=True)
    s.ensure_dirs()

    from .events.bus import EventBus
    from .models.enums import Priority
    from .models.task import AcceptanceCriterion, Task
    from .runtime.task_graph import run_task

    repo = repo.resolve()
    repo.mkdir(parents=True, exist_ok=True)

    crits: list[AcceptanceCriterion] = []
    checks = check or []
    for i, ctext in enumerate(criterion or []):
        crits.append(AcceptanceCriterion(text=ctext, check=checks[i] if i < len(checks) else None))

    task = Task(
        title=title,
        description=description,
        priority=Priority.HIGH,
        acceptance_criteria=crits,
    )

    bus = EventBus(s.data_dir / "events.db")
    bus.subscribe(lambda e: console.print(f"[dim]· {e.type.value}[/dim] {e.payload}"))

    console.print(Panel.fit(f"[bold]{task.id}[/bold]  {title}\nrepo: {repo}\nrole: {role}", title="run-task"))
    result = run_task(
        task,
        workspace_root=str(repo),
        agent_role=role,
        settings=s,
        max_attempts=attempts,
    )

    for ev in result.events:
        bus.emit_dict(ev)

    colour = {"done": "green", "blocked": "yellow", "escalated": "red", "error": "red"}.get(result.outcome, "white")
    console.print(Panel(
        textwrap.dedent(f"""\
        outcome:  [{colour}]{result.outcome.upper()}[/{colour}]
        attempts: {result.attempts}
        branch:   {result.branch}
        commit:   {result.commit_hash or '-'}

        [bold]agent summary[/bold]
        {result.agent_summary or '(none)'}

        [bold]verification[/bold]
        {result.verification_render or '(not run)'}
        """),
        title=f"result {task.id}",
    ))
    bus.close()
    raise typer.Exit(0 if result.ok else 1)


@app.command()
def demo(
    keep: bool = typer.Option(False, "--keep", help="Keep the scratch repo after the run."),
) -> None:
    """Self-contained Milestone-1 smoke test: scaffold a tiny repo and run one task."""
    load_env()
    s = get_settings(reload=True)
    s.ensure_dirs()

    from .events.bus import EventBus
    from .models.enums import Priority
    from .models.task import AcceptanceCriterion, Task
    from .runtime.task_graph import run_task

    scratch = s.workspace_dir / "demo-repo"
    if scratch.exists():
        import shutil

        shutil.rmtree(scratch, ignore_errors=True)
    (scratch / "src").mkdir(parents=True, exist_ok=True)
    (scratch / "src" / "calc.py").write_text(
        '"""Tiny calculator."""\n\n\ndef add(a, b):\n    return a + b\n',
        encoding="utf-8",
    )
    (scratch / "tests").mkdir(exist_ok=True)
    (scratch / "tests" / "test_calc.py").write_text(
        "import sys, os\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))\n"
        "from calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    task = Task(
        title="Add a subtract() function to the calculator",
        description=(
            "Add `subtract(a, b)` to src/calc.py returning a - b. "
            "Add a pytest test for it in tests/test_calc.py. Keep add() working."
        ),
        priority=Priority.HIGH,
        acceptance_criteria=[
            AcceptanceCriterion(
                text="subtract(5, 2) == 3",
                check="python -c \"import sys; sys.path.insert(0,'src'); from calc import subtract; assert subtract(5,2)==3\"",
            ),
            AcceptanceCriterion(text="the full test suite passes"),
        ],
    )

    bus = EventBus(s.data_dir / "events.db")
    bus.subscribe(lambda e: console.print(f"[dim]· {e.type.value}[/dim]"))

    console.print(Panel.fit(f"scratch repo: {scratch}", title="aamt demo"))
    result = run_task(
        task, workspace_root=str(scratch), agent_role="backend", settings=s,
        project_summary="A tiny arithmetic library used to smoke-test the agent loop.",
    )
    for ev in result.events:
        bus.emit_dict(ev)

    console.rule("log")
    for line in result.log:
        console.print(line)
    console.rule("verdict")
    colour = {"done": "green"}.get(result.outcome, "red")
    console.print(f"[{colour}]{result.outcome.upper()}[/{colour}] after {result.attempts} attempt(s); commit {result.commit_hash or '-'}")
    console.print(result.verification_render)

    bus.close()
    if not keep:
        console.print(f"[dim](scratch repo left at {scratch}; use a fresh run to reset)[/dim]")
    raise typer.Exit(0 if result.ok else 1)


def _prepare_repo(repo: str, workspace_dir: Path) -> Path:
    """Accept a local path or a git URL; clone URLs into the workspace dir."""
    if repo.endswith(".git") or repo.startswith(("http://", "https://", "git@")):
        import subprocess

        name = repo.rstrip("/").split("/")[-1].removesuffix(".git")
        dest = (workspace_dir / name).resolve()
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            console.print(f"[dim]cloning {repo} -> {dest}[/dim]")
            subprocess.run(["git", "clone", repo, str(dest)], check=True)
        return dest
    p = Path(repo).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _print_backlog(store) -> None:
    from .models.enums import BacklogItemKind

    tasks = store.list_tasks()
    table = Table(title="backlog", show_lines=False)
    table.add_column("id"); table.add_column("kind"); table.add_column("role")
    table.add_column("pri"); table.add_column("status"); table.add_column("title")
    table.add_column("deps")
    for t in tasks:
        if t.kind not in (BacklogItemKind.TASK,):
            continue
        table.add_row(
            t.id, t.kind.value, t.role or "-", t.priority.value, t.status.value,
            (t.title[:60]), ",".join(d[-4:] for d in t.dependencies) or "-",
        )
    console.print(table)


@app.command()
def plan(
    problem: str = typer.Option(..., "--problem", "-p", help="The problem statement."),
    repo: str = typer.Option(..., "--repo", "-r", help="Local path or git URL for the shared repo."),
    name: str = typer.Option("project", "--name", "-n"),
    acceptance: list[str] = typer.Option(None, "--acceptance", "-a", help="Project acceptance criterion (repeatable)."),
    language: str = typer.Option(None, "--language"),
    framework: str = typer.Option(None, "--framework"),
) -> None:
    """Create a project, form the team, generate the backlog, and plan sprint 1 (no execution)."""
    load_env()
    s = get_settings(reload=True)
    from .models.project import ProjectConstraints
    from .orchestrator import Orchestrator

    repo_path = _prepare_repo(repo, s.workspace_dir)
    orch = Orchestrator(s)
    project = orch.create_project(
        name=name,
        problem_statement=problem,
        repo_path=str(repo_path),
        acceptance_criteria=acceptance or [],
        constraints=ProjectConstraints(language=language, framework=framework),
    )
    console.print(Panel.fit(f"[bold]{project.id}[/bold] {name}\nrepo: {repo_path}", title="project"))

    with console.status("generating backlog…"):
        orch.bootstrap(project)
    _print_backlog(orch.store)

    with console.status("planning sprint 1…"):
        planned = orch.plan_next_sprint(orch.store.get_project())
    console.print(Panel(
        f"goal: {planned.sprint.goal}\n\n" + "\n".join(planned.plan.rationale)
        + (f"\n\ndeferred: {len(planned.plan.deferred)}" if planned.plan.deferred else ""),
        title=f"sprint {planned.sprint.number} plan ({len(planned.plan.task_ids)} tasks)",
    ))
    orch.close()


@app.command()
def build(
    problem: str = typer.Option(..., "--problem", "-p", help="The problem statement."),
    repo: str = typer.Option(..., "--repo", "-r", help="Local path or git URL for the shared repo."),
    name: str = typer.Option("project", "--name", "-n"),
    acceptance: list[str] = typer.Option(None, "--acceptance", "-a"),
    language: str = typer.Option(None, "--language"),
    framework: str = typer.Option(None, "--framework"),
    max_sprints: int = typer.Option(None, "--max-sprints"),
) -> None:
    """Full loop: problem statement -> team -> backlog -> sprints -> (attempted) working software."""
    load_env()
    s = get_settings(reload=True)
    from .models.project import ProjectConstraints
    from .orchestrator import Orchestrator

    repo_path = _prepare_repo(repo, s.workspace_dir)
    orch = Orchestrator(s)
    orch.bus.subscribe(lambda e: console.print(f"[dim]· {e.type.value}[/dim] "
                                               f"{ {k: v for k, v in e.payload.items() if k in ('title','role','goal','number','passed','hash','reason')} }"))

    project = orch.run(
        name=name,
        problem_statement=problem,
        repo_path=str(repo_path),
        acceptance_criteria=acceptance or [],
        constraints=ProjectConstraints(language=language, framework=framework),
        max_sprints=max_sprints,
    )

    _print_backlog(orch.store)
    sprints = orch.store.list_sprints()
    table = Table(title="sprints")
    table.add_column("#"); table.add_column("goal"); table.add_column("done/planned"); table.add_column("velocity")
    for sp in sprints:
        rv = sp.review
        table.add_row(
            str(sp.number), (sp.goal or "")[:50],
            f"{len(rv.completed)}/{len(rv.planned)}" if rv else "-",
            f"{rv.velocity:g}" if rv else "-",
        )
    console.print(table)
    console.print(Panel.fit(f"project status: [bold]{project.status.value}[/bold]", title="done"))
    orch.close()
    raise typer.Exit(0 if project.status.value == "COMPLETED" else 1)


@app.command()
def status() -> None:
    """Show the persisted project, backlog and sprint state."""
    load_env()
    s = get_settings(reload=True)
    from .orchestrator import Orchestrator

    orch = Orchestrator(s)
    project = orch.store.get_project()
    if not project:
        console.print("[yellow]no project in state store[/yellow]")
        raise typer.Exit(1)
    console.print(Panel.fit(
        f"[bold]{project.id}[/bold] {project.name}\n"
        f"status: {project.status.value}   sprints: {project.sprint_count}\n"
        f"repo: {project.repo_path}",
        title="project",
    ))
    _print_backlog(orch.store)
    orch.close()


@app.command()
def report(
    kind: str = typer.Option("final", "--kind", "-k", help="final | sprint | agent | timeline | daily"),
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
) -> None:
    """Render a project report from persisted state + the event log."""
    load_env()
    s = get_settings(reload=True)
    from .events.bus import EventBus
    from .reporting import (
        agent_report, daily_report, final_report, project_timeline, sprint_report,
    )
    from .state.store import ProjectStore

    store = ProjectStore(s.state_db_path)
    bus = EventBus(s.data_dir / "events.db")
    project = store.get_project()
    fns = {
        "final": lambda: final_report(store, bus),
        "sprint": lambda: sprint_report(store),
        "agent": lambda: agent_report(store, bus),
        "timeline": lambda: project_timeline(bus, project.id if project else None),
        "daily": lambda: daily_report(store, bus),
    }
    if kind not in fns:
        console.print(f"[red]unknown kind {kind!r}[/red]; choose {', '.join(fns)}")
        raise typer.Exit(2)
    text = fns[kind]()
    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"[green]wrote {out}[/green]")
    else:
        from rich.markdown import Markdown

        console.print(Markdown(text))
    store.close(); bus.close()


@app.command()
def pause() -> None:
    """Ask a running `aamt build`/`resume-run` to stop after the current task."""
    _signal("PAUSE")


@app.command()
def resume() -> None:
    """Clear a previous pause so the next `resume-run` proceeds."""
    _signal("RUN")


@app.command()
def stop() -> None:
    """Ask a running orchestration to abandon the project."""
    _signal("STOP")


def _signal(state: str) -> None:
    load_env()
    s = get_settings(reload=True)
    s.ensure_dirs()
    (s.data_dir / s.control_file).write_text(state, encoding="utf-8")
    console.print(f"control -> [bold]{state}[/bold]")


@app.command("resume-run")
def resume_run(max_sprints: int = typer.Option(None, "--max-sprints")) -> None:
    """Continue the persisted project's sprint loop from where it stopped."""
    load_env()
    s = get_settings(reload=True)
    from .orchestrator import Orchestrator

    orch = Orchestrator(s)
    orch.bus.subscribe(lambda e: console.print(f"[dim]· {e.type.value}[/dim]"))
    project = orch.resume(max_sprints=max_sprints)
    console.print(Panel.fit(f"status: [bold]{project.status.value}[/bold]", title="resumed run"))
    orch.close()


@app.command()
def tui() -> None:
    """Launch the AGENT.OS terminal dashboard."""
    load_env()
    from .tui.app import AgentOSApp

    AgentOSApp().run()


if __name__ == "__main__":
    app()
